"""Source-attribution ESTIMATE service. Wording rule: results are 'likely contributors' /
'source-attribution estimates' — association only, never a confirmed cause."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.analytics.attribution_engine import METHOD, Candidate, rank_contributors
from app.core.config import get_settings
from app.core.logging import log
from app.core.parameters import EVENT_TYPES, PARAMETERS
from app.core.timeutil import bucket_delta
from app.repositories import analytics as arepo
from app.repositories import events as event_repo
from app.repositories import factories as factory_repo
from app.services.features import grid_frame

logger = logging.getLogger("enviropulse.attribution")
DISCLAIMER = "Source-attribution estimate based on statistical association. Not proof of causation."
UNAVAILABLE_CONTEXT = [{"variable": "weather (wind speed/direction, mixing height)",
                        "status": "unavailable", "reason": "No weather source is configured in this prototype."}]


def _window(anomaly_ts: datetime) -> tuple[datetime, datetime]:
    return anomaly_ts - get_settings().attribution_window_buckets * bucket_delta(), anomaly_ts


def build_candidates(db: Session, zone_id: str, start: datetime, end: datetime):
    factories = factory_repo.zone_factories(db, zone_id)
    names = [f"factory_{f['id']}_output" for f in factories] + [f"event_{t}_active" for t in EVENT_TYPES]
    frame = grid_frame(db, zone_id, names, start, end)
    events = event_repo.events_overlapping(db, zone_id, start, end + bucket_delta())
    cands = [Candidate("factory", f["id"], f["name"], frame[f"factory_{f['id']}_output"], "continuous", "%")
             for f in factories]
    for et in EVENT_TYPES:
        of_type = [e for e in events if e["type"] == et]
        if not of_type:
            continue
        latest = of_type[-1]
        label = f"{et.replace('_', ' ').capitalize()}: {latest['description']}"
        cands.append(Candidate("event", str(latest["id"]), label, frame[f"event_{et}_active"], "binary", ""))
    return cands


def attribute_anomaly(db: Session, anomaly: dict) -> int:
    start, end = _window(anomaly["timestamp"])
    target = grid_frame(db, anomaly["zone_id"], [f"{anomaly['parameter']}_mean"], start, end).iloc[:, 0]
    ranked = rank_contributors(target, build_candidates(db, anomaly["zone_id"], start, end))
    rows = [{**r, "anomaly_id": anomaly["id"], "time_window_start": start, "time_window_end": end,
             "method_version": get_settings().attribution_version} for r in ranked[:6]]
    arepo.insert_attributions(db, rows)
    log(logger, logging.INFO, "attribution estimate stored", anomaly_id=anomaly["id"], candidates=len(rows))
    return len(rows)


def attribute_pending(db: Session, zone_id: str, start: datetime, end: datetime) -> int:
    n = 0
    for a in arepo.anomalies_without_attribution(db, zone_id, start, end):
        attribute_anomaly(db, a)
        n += 1
    return n


def attribution_view(db: Session, zone_id: str, parameter: str | None, anomaly_id: int | None,
                     start: datetime, end: datetime) -> dict:
    base = {"zone_id": zone_id, "label": "ESTIMATE", "disclaimer": DISCLAIMER, "method": METHOD,
            "method_version": get_settings().attribution_version, "unavailable_context": UNAVAILABLE_CONTEXT}
    if anomaly_id is not None:
        anomaly = arepo.get_anomaly(db, anomaly_id)
        if not anomaly or anomaly["zone_id"] != zone_id:
            return {**base, "status": "ANOMALY_NOT_FOUND", "anomaly": None, "contributors": [], "scatter": None}
    else:
        found = arepo.list_anomalies(db, zone_id, parameter, start, end, limit=1)
        if not found:
            return {**base, "status": "NO_ANOMALY_IN_RANGE", "anomaly": None, "contributors": [], "scatter": None,
                    "message": "No anomaly in the selected zone, parameter and time range, so there is nothing to explain."}
        anomaly = found[0]
    contributors = arepo.attributions_for(db, anomaly["id"])
    scatter = None
    top_factory = next((c for c in contributors if c["contributor_type"] == "factory"), None)
    if top_factory:
        w0, w1 = contributors[0]["time_window_start"], contributors[0]["time_window_end"]
        lag = top_factory["best_lag_windows"] or 0
        frame = grid_frame(db, zone_id, [f"factory_{top_factory['contributor_id']}_output",
                                         f"{anomaly['parameter']}_mean"], w0, w1)
        x = frame.iloc[:, 0].shift(lag)
        y = frame.iloc[:, 1]
        pts = [{"timestamp": ts, "x": float(xv), "y": float(yv), "is_anomaly_window": ts == anomaly["timestamp"]}
               for ts, xv, yv in zip(frame.index, x, y) if xv == xv and yv == yv]
        sp = PARAMETERS[anomaly["parameter"]]
        scatter = {"factory_id": top_factory["contributor_id"], "factory_name": top_factory["contributor_name"],
                   "x_label": f"{top_factory['contributor_name']} production level (t-{lag} window)", "x_unit": "%",
                   "y_label": f"{sp.label} zone mean", "y_unit": sp.unit, "lag_windows": lag,
                   "correlation": top_factory["correlation"], "points": pts,
                   "caption": "Association only — not proof of causation."}
    return {**base, "status": "OK", "anomaly": anomaly, "contributors": contributors, "scatter": scatter}
