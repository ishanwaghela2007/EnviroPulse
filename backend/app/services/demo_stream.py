"""Demo stream: each tick advances the SIMULATED clock by one window and moves the new records through
the real pipeline: connectors -> ingestion/validation -> alignment -> anomaly -> attribution -> alerts ->
forecast. Accelerated replay: one tick = one 15-min window of simulated time (documented in README).
Simulated outages make a connector fail, so source health goes DEGRADED -> OFFLINE honestly."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.connectors import events as events_conn
from app.connectors import factory as factory_conn
from app.connectors import water_sensor
from app.connectors.base import ConnectorError
from app.connectors.simulated import SIM_AIR, fetch_air
from app.core import redis as rcache
from app.core.config import get_settings
from app.core.database import pipeline_lock
from app.core.logging import log
from app.core.timeutil import bucket_delta, utcnow
from app.repositories import analytics as arepo
from app.repositories import source_health as sh_repo
from app.services import ingestion, pipeline
from app.simulation.stream import GOLDEN_TICKS, SimulationStream

logger = logging.getLogger("enviropulse.demo")
STATE_KEY, OUTAGE_KEY = "demo:stream", "demo:outages"
GOLDEN_STORY = {
    1: "Normal readings arrive for all zones.", 2: "Normal readings.", 3: "Normal readings.",
    4: "Apex Organics production rises (Zone A).",
    5: "PM2.5 rises one window later: anomaly detected; first threshold breach (alert needs 3).",
    6: "Construction event starts nearby; second consecutive breach.",
    7: "Third consecutive breach: persistence met, so an alert is created.",
    8: "Breach continues: the same alert is updated (no duplicate).",
    9: "Breach continues: alert updated.", 10: "Production back to nominal; PM2.5 still high (1-window lag).",
    11: "PM2.5 back within limits (1 of 2 normal windows needed to close the episode).",
    12: "Second normal window: the alert episode is resolved.",
}
_stream_cache: dict[tuple, SimulationStream] = {}


class DemoError(RuntimeError):
    pass


def get_stream(state: dict) -> SimulationStream:
    key = (state["seed"], state["history_end"])
    if key not in _stream_cache:
        _stream_cache.clear()
        _stream_cache[key] = SimulationStream(state["seed"], datetime.fromisoformat(state["history_end"]))
    return _stream_cache[key]


def init_state(db: Session, history_end: datetime) -> None:
    arepo.set_state(db, STATE_KEY, {"seed": get_settings().random_seed, "history_end": history_end.isoformat(),
                                    "next_window": (history_end + bucket_delta()).isoformat(), "tick": 0})
    arepo.set_state(db, OUTAGE_KEY, {})


def status(db: Session) -> dict:
    state = arepo.get_state(db, STATE_KEY)
    if not state:
        return {"initialised": False}
    tick = state["tick"]
    return {"initialised": True, "tick": tick, "next_window": state["next_window"], "golden_ticks": GOLDEN_TICKS,
            "golden_complete": tick >= GOLDEN_TICKS, "last_step": GOLDEN_STORY.get(tick),
            "next_step": GOLDEN_STORY.get(tick + 1), "outages": arepo.get_state(db, OUTAGE_KEY) or {},
            "label": "SIMULATED DEMO STREAM", "clock": "accelerated replay: 1 tick = 1 window of simulated time"}


def set_outage(db: Session, source: str, enabled: bool) -> dict:
    pipeline_lock(db)
    valid = {SIM_AIR.name, water_sensor.INFO.name, factory_conn.INFO.name, events_conn.INFO.name}
    if source not in valid:
        raise DemoError(f"Unknown simulated source '{source}'. Valid: {sorted(valid)}")
    outages = arepo.get_state(db, OUTAGE_KEY) or {}
    outages[source] = enabled
    arepo.set_state(db, OUTAGE_KEY, outages)
    log(logger, logging.WARNING if enabled else logging.INFO, "simulated outage toggled", source=source,
        enabled=enabled)
    return outages


def tick(db: Session) -> dict:
    pipeline_lock(db)  # concurrent ticks queue here; each then reads the state the previous one committed
    state = arepo.get_state(db, STATE_KEY)
    if not state:
        raise DemoError("Demo stream is not initialised. Run the seed first.")
    ts = datetime.fromisoformat(state["next_window"])
    if ts + bucket_delta() > utcnow():
        raise DemoError("The simulated clock has caught up with real time. Reset the demo to replay it.")
    stream, outages = get_stream(state), arepo.get_state(db, OUTAGE_KEY) or {}
    received_at = ts + timedelta(minutes=5)  # simulated receive time (accelerated replay)
    results: dict = {}
    jobs = [
        (SIM_AIR.name, lambda o: fetch_air(stream, ts, o), lambda recs: ingestion.ingest_observations(db, recs, received_at)),
        (water_sensor.INFO.name, lambda o: water_sensor.fetch(stream, ts, o),
         lambda recs: ingestion.ingest_observations(db, recs, received_at)),
        (factory_conn.INFO.name, lambda o: factory_conn.fetch(stream, ts, o),
         lambda recs: ingestion.ingest_factory_outputs(db, recs, received_at)),
        (events_conn.INFO.name, lambda o: events_conn.fetch(stream, ts, o), lambda recs: ingestion.ingest_events(db, recs)),
    ]
    for name, fetch, ingest in jobs:
        try:
            batch = fetch(bool(outages.get(name)))
            res = ingest(batch.records)
            sh_repo.record_success(db, name, utcnow(), round(batch.latency_ms, 2), res.inserted, ts, "SIMULATED")
            rcache.cache_set(f"lkg:{name}", {"window": ts, "records": res.inserted, "stored_at": utcnow()})
            results[name] = {"status": "ok", **{k: v for k, v in res.to_dict().items()
                                                if k in ("received", "inserted", "duplicates", "quarantined")}}
        except ConnectorError as exc:
            new_status = sh_repo.record_failure(db, name, utcnow(), str(exc))
            log(logger, logging.ERROR, "source failure", source=name, status=new_status, error=str(exc))
            results[name] = {"status": "failed", "source_status": new_status, "error": str(exc),
                             "last_known_good": rcache.cache_get(f"lkg:{name}")}
    db.flush()
    processed = pipeline.process_pending(db)
    arepo.set_state(db, STATE_KEY, {**state, "next_window": (ts + bucket_delta()).isoformat(), "tick": state["tick"] + 1})
    rcache.bump_data_version({"type": "demo_tick", "window": ts})
    log(logger, logging.INFO, "demo tick", tick=state["tick"] + 1, window=ts)
    return {"tick": state["tick"] + 1, "window": ts, "story": GOLDEN_STORY.get(state["tick"] + 1),
            "sources": results,
            "pipeline": [{"zone_id": p["zone_id"], "new_anomalies": p["new_anomalies"],
                          "attributions": p["attributions"], "alerts": p["alerts"]} for p in processed]}
