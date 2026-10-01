"""Repeatable seed: static world (zones, sensors, factories, thresholds, source registry) + 14 days of
SIMULATED history pushed through the real ingestion pipeline (including deliberately malformed and
duplicate records), then the full analytics pipeline over the history.

Usage:  python -m app.seed.seed_database            (fails if data already exists)
        python -m app.seed.reset_demo               (truncate + reseed)"""
import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import text

from app.connectors import cpcb
from app.connectors.registry import EXTERNAL_SOURCES, SIMULATED_SOURCES
from app.core import redis as rcache
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import configure_logging, log
from app.core.timeutil import bucket_delta, floor_bucket, utcnow
from app.repositories import alerts as alert_repo
from app.repositories import analytics as arepo
from app.repositories import factories as factory_repo
from app.repositories import sensors as sensor_repo
from app.repositories import source_health as sh_repo
from app.repositories import zones as zone_repo
from app.services import demo_stream, ingestion, pipeline
from app.simulation import world
from app.simulation.stream import SimulationStream

logger = logging.getLogger("enviropulse.seed")
CHUNK_WINDOWS = 24  # ingest 6 h at a time with a near-real-time receive clock (so history is not STALE)


def seed_static(db) -> None:
    for z in world.ZONES:
        zone_repo.insert_zone(db, z, world.BOUNDARY_NOTE)
    for sid, zone, stype, name, lat, lon, _ in world.SENSORS:
        resolved = zone_repo.zone_for_point(db, lat, lon)
        if resolved != zone:
            raise RuntimeError(f"sensor {sid} geometry resolves to {resolved}, expected {zone}")
        source = "sim_air" if stype == "air" else "sim_water"
        sensor_repo.upsert_sensor(db, sid, resolved, stype, name, lat, lon, source,
                                  world.AIR if stype == "air" else world.WATER)
    for f in world.FACTORIES:
        factory_repo.insert_factory(db, f, zone_repo.zone_for_point(db, f["lat"], f["lon"]))
    for zone, p, value, direction, persist, conf, sev, action, basis in world.THRESHOLDS:
        alert_repo.insert_threshold(db, {"zone_id": zone, "parameter": p, "threshold_value": value,
                                         "direction": direction, "persistence_windows": persist,
                                         "min_confidence": conf, "severity": sev, "action_text": action,
                                         "basis": basis})
    for s in SIMULATED_SOURCES:
        sh_repo.ensure_source(db, s.name, s.label, s.category, True, "SIMULATED")
    for s in EXTERNAL_SOURCES:
        msg = cpcb.STATUS_MESSAGE if s.name == "cpcb" else \
            f"{'OPENAQ_API_KEY' if s.name == 'openaq' else 'OGD_API_KEY'} not configured; source not fetched."
        sh_repo.ensure_source(db, s.name, s.label, s.category, False, "OFFLINE", msg)


def bad_records(ts) -> list[dict]:
    """Deliberately malformed inputs: every one must be quarantined, none silently dropped."""
    base = {"source": "sim_air", "sensor_id": "a_air_1", "timestamp": ts.isoformat(), "unit": "µg/m³"}
    return [
        {**base, "parameter": "pm25", "value": -12.0, "source_record_id": "bad:negative"},
        {**base, "parameter": "pm25", "value": "high", "source_record_id": "bad:text"},
        {**base, "parameter": "pm25", "value": 30.0, "unit": "ppm", "source_record_id": "bad:unit"},
        {**base, "parameter": "benzene", "value": 3.0, "source_record_id": "bad:param"},
        {**base, "parameter": "pm25", "value": 30.0, "timestamp": (ts + timedelta(days=2)).isoformat(),
         "source_record_id": "bad:future"},
        {"source": "sim_air", "parameter": "pm25", "value": 40.0, "timestamp": ts.isoformat(), "unit": "µg/m³",
         "latitude": 18.52, "longitude": 73.85, "source_record_id": "bad:outside_zone"},
        {"source": "sim_air", "timestamp": ts.isoformat(), "value": 10.0, "source_record_id": "bad:no_param"},
    ]


def seed(verbose: bool = True) -> dict:
    s = get_settings()
    d = bucket_delta()
    t0 = time.perf_counter()
    history_end = floor_bucket(utcnow()) - timedelta(hours=s.history_lag_hours)
    history_start = history_end - timedelta(days=s.history_days) + d
    with session_scope() as db:
        if db.execute(text("SELECT count(*) FROM zones")).scalar():
            raise SystemExit("Database already seeded. Use `python -m app.seed.reset_demo` to reset and reseed.")
        seed_static(db)
    stream = SimulationStream(s.random_seed, history_end)
    totals = {"readings": 0, "duplicates": 0, "quarantined": 0, "factory_outputs": 0, "events": 0}
    ts, first = history_start, True
    while ts <= history_end:
        chunk = [ts + i * d for i in range(CHUNK_WINDOWS) if ts + i * d <= history_end]
        received_at = chunk[-1] + timedelta(minutes=5)
        obs, fac, ev = [], [], []
        for w in chunk:
            air, water = stream.air_water_records(w)
            obs += air + water
            fac += stream.factory_records(w)
            ev += stream.event_records(w)
        if first:
            obs += bad_records(chunk[0]) + obs[:20]  # malformed records + a re-sent (duplicate) batch
            first = False
        with session_scope() as db:
            r = ingestion.ingest_observations(db, obs, received_at)
            f = ingestion.ingest_factory_outputs(db, fac, received_at)
            e = ingestion.ingest_events(db, ev)
        totals["readings"] += r.inserted
        totals["duplicates"] += r.duplicates
        totals["quarantined"] += r.quarantined + f.quarantined + e.quarantined
        totals["factory_outputs"] += f.inserted
        totals["events"] += e.inserted
        ts = chunk[-1] + d
    with session_scope() as db:
        for z in world.ZONES:
            pipeline.process_zone(db, z["id"], history_start, history_end)
        _, newest = pipeline.pending_ranges(db, None)
        arepo.set_state(db, pipeline.WATERMARK_KEY, {"created_at": newest.isoformat()})
        now = utcnow()
        for src in SIMULATED_SOURCES:
            sh_repo.record_success(db, src.name, now, 0.0, 0, history_end, "SIMULATED")
        demo_stream.init_state(db, history_end)
        totals["anomalies"] = db.execute(text("SELECT count(*) FROM anomalies")).scalar()
        totals["alerts"] = db.execute(text("SELECT count(*) FROM alerts")).scalar()
        totals["attributions"] = db.execute(text("SELECT count(*) FROM attributions")).scalar()
    rcache.flush_namespace()
    rcache.bump_data_version({"type": "seed"})
    totals.update(history_start=history_start.isoformat(), history_end=history_end.isoformat(),
                  seconds=round(time.perf_counter() - t0, 1))
    log(logger, logging.INFO, "seed complete", **totals)
    if verbose:
        print(totals)
    return totals


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    argparse.ArgumentParser(description="Seed EnviroPulse demo data").parse_args()
    seed()
