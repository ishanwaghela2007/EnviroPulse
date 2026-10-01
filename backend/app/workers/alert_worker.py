"""Alert worker: re-evaluates thresholds for every zone up to its latest window (idempotent; the engine
keeps a per-rule watermark so no window is evaluated twice)."""
from app.core.database import session_scope
from app.core.timeutil import floor_bucket
from app.repositories import readings as reading_repo
from app.repositories import zones as zone_repo
from app.services import alerts as alert_service


def run() -> dict:
    out = {}
    with session_scope() as db:
        for z in zone_repo.list_zones(db):
            latest = reading_repo.latest_reading_time(db, z["id"])
            if latest:
                out[z["id"]] = alert_service.evaluate_zone(db, z["id"], floor_bucket(latest))
    return out
