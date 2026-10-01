"""Schema / type / range / missing / stale validation. Pure functions: no database access.

Outcome of every record is explicit:
  * rejected -> quarantined with a reason code (never silently dropped)
  * accepted -> normalized record with quality flag VALID | MISSING | SUSPICIOUS | STALE
Missing values stay None/NULL — never converted to zero."""
import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.parameters import EVENT_TYPES, FACTORY_METRICS, PARAMETERS
from app.core.timeutil import to_utc

VALID, MISSING, SUSPICIOUS, STALE = "VALID", "MISSING", "SUSPICIOUS", "STALE"
FUTURE_TOLERANCE = timedelta(minutes=5)
SEVERITIES = {"low", "medium", "high"}
_UNIT_ALIASES = {"µg/m³": "µg/m³", "ug/m3": "µg/m³", "µg/m3": "µg/m³", "ug/m³": "µg/m³", "micrograms/m3": "µg/m³",
                 "ph": "pH", "ntu": "NTU", "mg/l": "mg/L"}


@dataclass
class ValidationResult:
    accepted: bool
    record: dict | None = None
    reason: str | None = None


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = str(unit).strip()
    return _UNIT_ALIASES.get(u.lower(), _UNIT_ALIASES.get(u, u))


def parse_timestamp(raw) -> datetime:
    if isinstance(raw, datetime):
        return to_utc(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("timestamp must be an ISO-8601 string")
    return to_utc(datetime.fromisoformat(raw.strip().replace("Z", "+00:00")))


def parse_number(raw) -> float | None:
    """None for missing (None / '' / NaN). Raises ValueError for non-numeric values."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if isinstance(raw, bool):
        raise ValueError("boolean is not a numeric value")
    v = float(raw)
    if math.isnan(v):
        return None
    if math.isinf(v):
        raise ValueError("infinite value")
    return v


def fingerprint(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:24]


def validate_observation(raw: dict, now: datetime, stale_after: timedelta) -> ValidationResult:
    if not isinstance(raw, dict):
        return ValidationResult(False, reason="schema:not_an_object")
    for key in ("source", "timestamp", "parameter"):
        if raw.get(key) in (None, ""):
            return ValidationResult(False, reason=f"schema:missing_{key}")
    if "value" not in raw:
        return ValidationResult(False, reason="schema:missing_value_field")
    if not raw.get("sensor_id") and (raw.get("latitude") is None or raw.get("longitude") is None):
        return ValidationResult(False, reason="schema:missing_location")
    param = str(raw["parameter"]).strip().lower().replace(".", "")
    if param not in PARAMETERS:
        return ValidationResult(False, reason=f"schema:unknown_parameter:{raw['parameter']}")
    spec = PARAMETERS[param]
    unit = normalize_unit(raw.get("unit")) or spec.unit
    if unit != spec.unit:
        return ValidationResult(False, reason=f"type:unit_mismatch:{raw.get('unit')}")
    try:
        ts = parse_timestamp(raw["timestamp"])
    except (ValueError, TypeError):
        return ValidationResult(False, reason="type:invalid_timestamp")
    if ts > now + FUTURE_TOLERANCE:
        return ValidationResult(False, reason="range:timestamp_in_future")
    try:
        value = parse_number(raw["value"])
    except (ValueError, TypeError):
        return ValidationResult(False, reason="type:non_numeric_value")
    lat, lon = raw.get("latitude"), raw.get("longitude")
    if lat is not None or lon is not None:
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return ValidationResult(False, reason="type:invalid_coordinates")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return ValidationResult(False, reason="range:invalid_coordinates")

    flag, why = VALID, None
    if value is None:
        flag, why = MISSING, "value missing at source"
    else:
        lo, hi = spec.physical_range
        if not (lo <= value <= hi):
            return ValidationResult(False, reason=f"range:out_of_physical_range:{value}")
        plo, phi = spec.plausible_range
        if not (plo <= value <= phi):
            flag, why = SUSPICIOUS, f"outside plausible range {plo}–{phi} {spec.unit}"
    if flag == VALID and now - ts > stale_after:
        flag, why = STALE, f"older than {int(stale_after.total_seconds() // 60)} min when received"

    rid = raw.get("source_record_id") or fingerprint(raw["source"], raw.get("sensor_id"), lat, lon, ts.isoformat(), param)
    return ValidationResult(True, record={
        "source": str(raw["source"]), "source_record_id": str(rid), "sensor_id": raw.get("sensor_id"),
        "latitude": lat, "longitude": lon, "timestamp": ts, "original_timestamp": str(raw["timestamp"]),
        "parameter": param, "value": value, "unit": spec.unit, "quality_flag": flag, "quality_reason": why,
        "sensor_name": raw.get("sensor_name"),
    })


def validate_factory_output(raw: dict, now: datetime) -> ValidationResult:
    for key in ("source", "factory_id", "timestamp", "metric"):
        if raw.get(key) in (None, ""):
            return ValidationResult(False, reason=f"schema:missing_{key}")
    if raw["metric"] not in FACTORY_METRICS:
        return ValidationResult(False, reason=f"schema:unknown_metric:{raw['metric']}")
    try:
        ts = parse_timestamp(raw["timestamp"])
        value = parse_number(raw.get("value"))
    except (ValueError, TypeError):
        return ValidationResult(False, reason="type:invalid_timestamp_or_value")
    if ts > now + FUTURE_TOLERANCE:
        return ValidationResult(False, reason="range:timestamp_in_future")
    if value is not None and not (0 <= value <= 100):
        return ValidationResult(False, reason=f"range:production_level_out_of_range:{value}")
    return ValidationResult(True, record={"source": raw["source"], "factory_id": raw["factory_id"], "timestamp": ts,
                                          "metric": raw["metric"], "value": value,
                                          "unit": FACTORY_METRICS[raw["metric"]],
                                          "operating_state": raw.get("operating_state")})


def validate_event(raw: dict) -> ValidationResult:
    for key in ("source", "source_record_id", "type", "start_time", "latitude", "longitude", "severity"):
        if raw.get(key) in (None, ""):
            return ValidationResult(False, reason=f"schema:missing_{key}")
    if raw["type"] not in EVENT_TYPES:
        return ValidationResult(False, reason=f"schema:unknown_event_type:{raw['type']}")
    if raw["severity"] not in SEVERITIES:
        return ValidationResult(False, reason=f"schema:unknown_severity:{raw['severity']}")
    try:
        start = parse_timestamp(raw["start_time"])
        end = parse_timestamp(raw["end_time"]) if raw.get("end_time") else None
        lat, lon = float(raw["latitude"]), float(raw["longitude"])
    except (ValueError, TypeError):
        return ValidationResult(False, reason="type:invalid_event_fields")
    if end is not None and end < start:
        return ValidationResult(False, reason="range:end_before_start")
    return ValidationResult(True, record={"source": raw["source"], "source_record_id": str(raw["source_record_id"]),
                                          "type": raw["type"], "start_time": start, "end_time": end, "latitude": lat,
                                          "longitude": lon, "severity": raw["severity"],
                                          "description": raw.get("description") or raw["type"].replace("_", " ")})
