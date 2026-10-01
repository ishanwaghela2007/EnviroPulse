"""Pure validation rules: schema, type, range, missing, stale, suspicious."""
from datetime import datetime, timedelta, timezone

from app.services import validation as v

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
STALE = timedelta(hours=12)


def obs(**kw):
    base = {"source": "sim_air", "sensor_id": "a_air_1", "timestamp": "2026-09-30T11:50:00Z", "parameter": "pm25",
            "value": 42.5, "unit": "µg/m³", "source_record_id": "r1"}
    base.update(kw)
    return v.validate_observation(base, NOW, STALE)


def test_valid_observation_normalized_to_utc():
    r = obs(timestamp="2026-09-30T17:20:00+05:30")
    assert r.accepted and r.record["quality_flag"] == "VALID"
    assert r.record["timestamp"] == datetime(2026, 9, 30, 11, 50, tzinfo=timezone.utc)
    assert r.record["original_timestamp"] == "2026-09-30T17:20:00+05:30"


def test_missing_value_preserved_not_zero():
    for missing in (None, "", float("nan")):
        r = obs(value=missing)
        assert r.accepted and r.record["value"] is None and r.record["quality_flag"] == "MISSING"


def test_suspicious_and_stale_flags():
    assert obs(value=900).record["quality_flag"] == "SUSPICIOUS"
    assert obs(timestamp="2026-09-29T20:00:00Z").record["quality_flag"] == "STALE"


def test_rejections_have_reason_codes():
    cases = {
        "range:out_of_physical_range": obs(value=-5),
        "type:non_numeric_value": obs(value="abc"),
        "type:unit_mismatch": obs(unit="ppm"),
        "schema:unknown_parameter": obs(parameter="benzene"),
        "range:timestamp_in_future": obs(timestamp="2026-10-02T00:00:00Z"),
        "type:invalid_timestamp": obs(timestamp="yesterday"),
        "schema:missing_location": obs(sensor_id=None),
    }
    for code, r in cases.items():
        assert not r.accepted and r.reason.startswith(code), (code, r.reason)
    r = v.validate_observation({"source": "x", "timestamp": "2026-09-30T11:00:00Z", "parameter": "pm25"}, NOW, STALE)
    assert r.reason == "schema:missing_value_field"


def test_unit_aliases_and_fingerprint():
    r = obs(unit="ug/m3", source_record_id=None)
    assert r.accepted and r.record["unit"] == "µg/m³" and len(r.record["source_record_id"]) == 24
    assert obs(source_record_id=None).record["source_record_id"] == r.record["source_record_id"]


def test_factory_and_event_validation():
    ok = v.validate_factory_output({"source": "s", "factory_id": "f", "timestamp": "2026-09-30T11:00:00Z",
                                    "metric": "production_level", "value": 55}, NOW)
    assert ok.accepted
    bad = v.validate_factory_output({"source": "s", "factory_id": "f", "timestamp": "2026-09-30T11:00:00Z",
                                     "metric": "production_level", "value": 150}, NOW)
    assert not bad.accepted and "out_of_range" in bad.reason
    ev = {"source": "s", "source_record_id": "e1", "type": "construction", "start_time": "2026-09-30T10:00:00Z",
          "end_time": "2026-09-30T09:00:00Z", "latitude": 19.1, "longitude": 73.0, "severity": "low"}
    assert v.validate_event(ev).reason == "range:end_before_start"
    assert v.validate_event({**ev, "type": "earthquake"}).reason.startswith("schema:unknown_event_type")


def test_alert_recovery_deadband():
    """Recovery counts only clearly-normal windows (5 % inside the limit); hovering values hold the episode."""
    from app.services.alerts import _breached, _clearly_normal
    above = {"threshold_value": 100.0, "direction": "above"}
    below = {"threshold_value": 4.0, "direction": "below"}
    assert _breached(100.5, above) and not _breached(100.0, above)
    assert not _clearly_normal(97.0, above, 5.0) and _clearly_normal(95.0, above, 5.0)
    assert _breached(3.9, below) and not _clearly_normal(4.1, below, 5.0) and _clearly_normal(4.2, below, 5.0)
