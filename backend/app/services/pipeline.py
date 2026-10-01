"""Pipeline orchestration: ALIGN -> FEATURES/ANOMALY -> ATTRIBUTION -> ALERTS (-> FORECAST refresh).
Each stage is a separate service so the stages can later move to independent queue workers."""
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import redis as rcache
from app.core.database import pipeline_lock
from app.core.logging import log
from app.core.parameters import PARAMETERS
from app.core.timeutil import floor_bucket
from app.repositories import analytics as arepo
from app.services import alerts as alert_service
from app.services import attribution as attribution_service
from app.services import forecast as forecast_service
from app.services.alignment import align_zone
from app.services.anomaly import run_anomaly_detection

logger = logging.getLogger("enviropulse.pipeline")
WATERMARK_KEY = "pipeline:watermark"


def process_zone(db: Session, zone_id: str, start: datetime, end: datetime, refresh_forecasts: bool = True) -> dict:
    start, end = floor_bucket(start), floor_bucket(end)
    out = {"zone_id": zone_id, "start": start, "end": end}
    out["alignment"] = align_zone(db, zone_id, start, end)
    out["new_anomalies"] = sum(len(run_anomaly_detection(db, zone_id, p, start, end)) for p in PARAMETERS)
    out["attributions"] = attribution_service.attribute_pending(db, zone_id, start, end)
    out["alerts"] = alert_service.evaluate_zone(db, zone_id, end, since=start)
    if refresh_forecasts:
        out["forecasts"] = {p: forecast_service.get_forecast(db, zone_id, p)["status"] for p in PARAMETERS}
    log(logger, logging.INFO, "pipeline run complete", zone=zone_id, anomalies=out["new_anomalies"],
        attributions=out["attributions"], alerts=out["alerts"])
    return out


def pending_ranges(db: Session, since: datetime | None) -> tuple[dict[str, tuple[datetime, datetime]], datetime | None]:
    """Zones/time spans touched by readings or factory outputs created after the watermark."""
    params = {"w": since or datetime(1970, 1, 1)}
    rows = db.execute(text("""
        SELECT zone_id, min(ts) lo, max(ts) hi, max(created) created FROM (
            SELECT zone_id, timestamp ts, created_at created FROM readings WHERE created_at > :w
            UNION ALL
            SELECT f.zone_id, o.timestamp, o.created_at FROM factory_outputs o JOIN factories f ON f.id=o.factory_id
            WHERE o.created_at > :w) t
        WHERE zone_id IS NOT NULL GROUP BY zone_id"""), params).all()
    ranges = {r.zone_id: (r.lo, r.hi) for r in rows}
    newest = max((r.created for r in rows), default=None)
    return ranges, newest


def process_pending(db: Session) -> list[dict]:
    pipeline_lock(db)
    state = arepo.get_state(db, WATERMARK_KEY) or {}
    since = datetime.fromisoformat(state["created_at"]) if state.get("created_at") else None
    ranges, newest = pending_ranges(db, since)
    results = [process_zone(db, z, lo, hi) for z, (lo, hi) in sorted(ranges.items())]
    if newest:
        arepo.set_state(db, WATERMARK_KEY, {"created_at": newest.isoformat()})
    if results:
        rcache.bump_data_version({"type": "pipeline", "zones": sorted(ranges)})
    return results
