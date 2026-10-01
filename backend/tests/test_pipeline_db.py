"""Database-backed pipeline tests: connection, geo assignment, ingestion, dedupe, features, anomalies,
threshold persistence, duplicate-alert prevention, insufficient history."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal, check_database, session_scope
from app.core.timeutil import utcnow
from app.repositories import alerts as alert_repo
from app.repositories import sensors as sensor_repo
from app.repositories import zones as zone_repo
from app.services import forecast as forecast_service
from app.services import ingestion, pipeline
from app.services.dashboard import anomaly_view, resolve_window


def hist_end(seeded):
    return datetime.fromisoformat(seeded["history_end"])


def test_database_connection_and_postgis(seeded):
    info = check_database()
    assert info["status"] == "ok" and info["postgis"].startswith("3")


def test_geo_zone_assignment_uses_postgis(db):
    assert zone_repo.zone_for_point(db, 19.108, 73.027) == "zone_a"
    assert zone_repo.zone_for_point(db, 19.060, 73.140) == "zone_b"
    assert zone_repo.zone_for_point(db, 18.52, 73.85) is None  # Pune: outside every configured zone


def test_unknown_station_assigned_by_coordinates_or_quarantined(db, seeded):
    ts = hist_end(seeded) - timedelta(minutes=10)
    inside = {"source": "test_station", "latitude": 19.115, "longitude": 73.030, "timestamp": ts.isoformat(),
              "parameter": "pm25", "value": 41.0, "unit": "µg/m³", "source_record_id": "t-in"}
    outside = {**inside, "latitude": 18.52, "longitude": 73.85, "source_record_id": "t-out"}
    res = ingestion.ingest_observations(db, [inside, outside], ts + timedelta(minutes=1))
    assert res.inserted == 1 and res.quarantine_reasons == {"geo:outside_configured_zones": 1}
    assert sensor_repo.get_sensor_map(db)["test_station:19.1150,73.0300"]["zone_id"] == "zone_a"
    db.execute(text("DELETE FROM readings WHERE source='test_station'"))
    db.execute(text("DELETE FROM sensors WHERE source='test_station'"))


def test_malformed_records_are_quarantined_not_dropped(db):
    reasons = {r[0] for r in db.execute(text("SELECT split_part(reason, ':', 1) || ':' || split_part(reason, ':', 2) "
                                             "FROM quarantined_records"))}
    assert {"range:out_of_physical_range", "type:non_numeric_value", "type:unit_mismatch",
            "schema:unknown_parameter", "range:timestamp_in_future", "geo:outside_configured_zones"} <= reasons


def test_duplicate_ingestion_is_rejected_by_constraint(db, seeded):
    rows = db.execute(text("SELECT source, sensor_id, timestamp, parameter, value, unit, source_record_id FROM readings "
                           "WHERE quality_flag='VALID' ORDER BY timestamp DESC LIMIT 5")).all()
    raws = [{**r._asdict(), "timestamp": r.timestamp.isoformat()} for r in rows]
    before = db.execute(text("SELECT count(*) FROM readings")).scalar()
    res = ingestion.ingest_observations(db, raws, rows[0].timestamp + timedelta(minutes=5))
    assert res.inserted == 0 and res.duplicates == 5
    assert db.execute(text("SELECT count(*) FROM readings")).scalar() == before


def test_missing_values_stay_null_and_excluded_from_means(db):
    flags = dict(db.execute(text("SELECT quality_flag, count(*) FROM readings GROUP BY 1")).all())
    assert flags.get("MISSING", 0) > 0 and flags.get("SUSPICIOUS", 0) > 0
    assert db.execute(text("SELECT count(*) FROM readings WHERE quality_flag='MISSING' AND value IS NOT NULL")).scalar() == 0
    # a suspicious 900 µg/m³ glitch never reaches the zone mean
    assert db.execute(text("SELECT max(value) FROM features WHERE feature_name='pm25_mean'")).scalar() < 500


def test_features_have_units_windows_and_correct_lags(db, seeded):
    t = hist_end(seeded)
    feats = {r.feature_name: r for r in db.execute(text(
        "SELECT feature_name, value, unit, source_window FROM features WHERE zone_id='zone_a' AND timestamp=:t"), {"t": t})}
    for name, unit in [("pm25_mean", "µg/m³"), ("pm25_rolling_mean", "µg/m³"), ("pm25_rolling_std", "µg/m³"),
                       ("pm25_deviation", "z-score"), ("pm25_rate_of_change", "µg/m³ per window"),
                       ("factory_fac_a1_output", "%"), ("factory_fac_a1_output_lag1", "%"),
                       ("event_construction_active", "flag"), ("aqi_indicative", "index"), ("pm25_confidence", "ratio")]:
        assert name in feats and feats[name].unit == unit and feats[name].source_window
    prev = db.execute(text("SELECT value FROM features WHERE zone_id='zone_a' AND feature_name='factory_fac_a1_output' "
                           "AND timestamp=:t"), {"t": t - timedelta(minutes=15)}).scalar()
    assert feats["factory_fac_a1_output_lag1"].value == pytest.approx(prev)


def test_anomaly_detected_for_zone_c_spike(db, seeded):
    spike_ts = hist_end(seeded) - timedelta(days=3, hours=8)
    a = db.execute(text("SELECT * FROM anomalies WHERE zone_id='zone_c' AND parameter='pm10' AND timestamp=:t"),
                   {"t": spike_ts}).first()
    assert a is not None and a.value > a.baseline_high and a.score > 3
    assert "baseline" in a.reason and "not a threshold decision" in a.reason


def test_transient_breach_does_not_create_alert(db, seeded):
    spike_ts = hist_end(seeded) - timedelta(days=3, hours=8)
    value = db.execute(text("SELECT value FROM features WHERE zone_id='zone_c' AND feature_name='pm10_mean' "
                            "AND timestamp=:t"), {"t": spike_ts}).scalar()
    assert value > 100  # the threshold WAS breached, for a single window
    covering = db.execute(text("SELECT count(*) FROM alerts WHERE zone_id='zone_c' AND parameter='pm10' "
                               "AND first_breach_at <= :t AND last_breach_at >= :t"), {"t": spike_ts}).scalar()
    assert covering == 0  # persistence = 3 -> no alert


def test_persistent_breach_created_one_alert_with_log(db):
    alerts = db.execute(text("SELECT * FROM alerts WHERE zone_id='zone_b' AND parameter='turbidity'")).all()
    assert len(alerts) == 1
    a = alerts[0]
    assert a.value > a.threshold == 25 and a.breach_windows >= 2 and a.status == "resolved" and not a.episode_open
    events = [e.event_type for e in db.execute(text("SELECT event_type FROM alert_events WHERE alert_id=:a ORDER BY id"),
                                               {"a": a.id})]
    assert events[:2] == ["created", "notification_dispatched"] and events[-1] == "resolved"


def test_zone_threshold_overrides_global(seeded):
    db = SessionLocal()
    try:
        alert_repo.insert_threshold(db, {"zone_id": "zone_c", "parameter": "pm25", "threshold_value": 45,
                                         "direction": "above", "persistence_windows": 2, "min_confidence": 0.5,
                                         "severity": "high", "action_text": "x", "basis": "zone override"})
        rules = [r for r in alert_repo.thresholds_for_zone(db, "zone_c") if r["parameter"] == "pm25"]
        assert len(rules) == 1 and rules[0]["threshold_value"] == 45
        assert [r for r in alert_repo.thresholds_for_zone(db, "zone_a") if r["parameter"] == "pm25"][0]["threshold_value"] == 60
    finally:
        db.rollback()
        db.close()


def test_database_blocks_duplicate_open_episode(seeded):
    db = SessionLocal()
    try:
        tid = db.execute(text("SELECT id FROM thresholds WHERE parameter='pm25'")).scalar()
        row = {"zone_id": "zone_a", "parameter": "pm25", "threshold_id": tid, "value": 70.0, "threshold": 60.0,
               "unit": "µg/m³", "direction": "above", "reason": "r", "source_context": None, "severity": "high",
               "action_text": "a", "breach_windows": 3, "first_breach_at": utcnow(), "last_breach_at": utcnow()}
        alert_repo.create_alert(db, row)
        with pytest.raises(IntegrityError):
            alert_repo.create_alert(db, row)
    finally:
        db.rollback()
        db.close()


def test_insufficient_history_returns_controlled_states(seeded):
    """A newly commissioned zone with 2.5 h of data: no fabricated baseline, anomaly or forecast."""
    end = datetime.fromisoformat(seeded["history_end"])
    with session_scope() as db:
        zone_repo.insert_zone(db, {"id": "zone_t", "name": "New zone", "description": "test", "polygon": [
            (72.80, 19.20), (72.82, 19.20), (72.82, 19.22), (72.80, 19.22), (72.80, 19.20)]}, "test")
        sensor_repo.upsert_sensor(db, "t_air_1", "zone_t", "air", "T-1", 19.21, 72.81, "sim_air", ["pm25"])
        raws = [{"source": "sim_air", "sensor_id": "t_air_1", "timestamp": (end - i * timedelta(minutes=15)).isoformat(),
                 "parameter": "pm25", "value": 40 + i % 3, "unit": "µg/m³", "source_record_id": f"t{i}"} for i in range(10)]
        ingestion.ingest_observations(db, raws, end + timedelta(minutes=5))
        pipeline.process_zone(db, "zone_t", end - timedelta(hours=3), end)
    with session_scope() as db:
        fc = forecast_service.get_forecast(db, "zone_t", "pm25")
        assert fc["status"] == "INSUFFICIENT_HISTORY" and fc["points"] == []
        view = anomaly_view(db, "zone_t", "pm25", resolve_window(db, "zone_t", "24h", None, None))
        assert view["status"] == "INSUFFICIENT_HISTORY" and view["anomalies"] == []
        for t in ("features", "readings", "aqi_snapshots", "water_observations", "pipeline_state"):
            col = "key" if t == "pipeline_state" else "zone_id"
            db.execute(text(f"DELETE FROM {t} WHERE {col} {'LIKE' if t == 'pipeline_state' else '='} :z"),
                       {"z": "alerts:zone_t:%" if t == "pipeline_state" else "zone_t"})
        db.execute(text("DELETE FROM sensors WHERE zone_id='zone_t'"))
        db.execute(text("DELETE FROM zones WHERE id='zone_t'"))
