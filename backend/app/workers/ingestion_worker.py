"""Air ingestion worker (scheduled): fetches configured external air sources. Sources without credentials
are reported OFFLINE (never faked); failures mark the source DEGRADED/OFFLINE and keep last-known-good."""
import logging

from app.connectors import ogd_aqi, openaq
from app.connectors.base import ConnectorError, ConnectorNotConfigured
from app.core import redis as rcache
from app.core.database import session_scope
from app.core.logging import log
from app.core.timeutil import utcnow
from app.repositories import source_health as sh_repo
from app.repositories import zones as zone_repo
from app.services import ingestion

logger = logging.getLogger("enviropulse.worker.ingestion")


def run_external_air() -> dict:
    out = {}
    with session_scope() as db:
        centroids = [(z["lat"], z["lon"]) for z in zone_repo.list_zones(db)]
    for name, fetch in (("openaq", lambda: openaq.fetch(centroids)), ("ogd_aqi", lambda: ogd_aqi.fetch())):
        with session_scope() as db:
            try:
                batch = fetch()
                res = ingestion.ingest_observations(db, batch.records, utcnow())
                sh_repo.record_success(db, name, utcnow(), round(batch.latency_ms, 1), res.inserted, res.max_ts,
                                       "HEALTHY")
                rcache.cache_set(f"lkg:{name}", {"records": res.inserted, "latest": res.max_ts, "stored_at": utcnow()})
                out[name] = "ok"
            except ConnectorNotConfigured as exc:
                sh_repo.set_status(db, name, "OFFLINE", str(exc))
                out[name] = "not_configured"
            except ConnectorError as exc:
                status = sh_repo.record_failure(db, name, utcnow(), str(exc))
                log(logger, logging.ERROR, "source failure", source=name, status=status, error=str(exc))
                out[name] = status
    return out
