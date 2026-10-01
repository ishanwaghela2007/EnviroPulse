"""Read-side services for the dashboard: window resolution, zone list, summary/KPIs, map layers, trends
and the anomaly view. Everything shown in the UI is computed here from stored data."""
import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.analytics.metrics import AQI_METHOD
from app.core import redis as rcache
from app.core.config import get_settings
from app.core.parameters import AIR_PARAMETERS, PARAMETERS, WATER_PARAMETERS
from app.core.timeutil import TIME_RANGES, bucket_delta, floor_bucket, to_utc
from app.repositories import alerts as alert_repo
from app.repositories import analytics as arepo
from app.repositories import events as event_repo
from app.repositories import factories as factory_repo
from app.repositories import readings as reading_repo
from app.repositories import sensors as sensor_repo
from app.repositories import source_health as sh_repo
from app.repositories import zones as zone_repo
from app.services import alerts as alert_service
from app.services.features import grid_frame
from app.services.ingestion import water_status

MAX_SPAN = timedelta(days=31)


class NotFound(LookupError):
    pass


class BadRequest(ValueError):
    pass


def _f(v):
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else v


def require_zone(db: Session, zone_id: str) -> dict:
    zone = zone_repo.get_zone(db, zone_id)
    if zone is None:
        raise NotFound(f"Zone '{zone_id}' not found.")
    return zone


def resolve_window(db: Session, zone_id: str, time_range: str | None, start: datetime | None,
                   end: datetime | None) -> dict:
    minutes = get_settings().default_time_window_minutes
    if start or end:
        if not (start and end):
            raise BadRequest("Provide both start and end, or neither.")
        start, end = to_utc(start), to_utc(end)
        if start >= end:
            raise BadRequest("start must be before end.")
        if end - start > MAX_SPAN:
            raise BadRequest("The requested span exceeds 31 days.")
        return {"start": floor_bucket(start), "end": floor_bucket(end), "time_range": None, "anchor": "explicit",
                "window_minutes": minutes}
    tr = time_range or "24h"
    latest = reading_repo.latest_reading_time(db, zone_id)
    end_ts = floor_bucket(latest) if latest else floor_bucket(datetime.now().astimezone())
    return {"start": end_ts - TIME_RANGES[tr] + bucket_delta(), "end": end_ts, "time_range": tr,
            "anchor": "latest_zone_data", "window_minutes": minutes}


def list_zones(db: Session) -> list[dict]:
    out = []
    for z in zone_repo.list_zones(db):
        aqi = arepo.latest_aqi(db, z["id"])
        counts = alert_repo.count_open(db, z["id"])
        out.append({**z, "centroid": {"lat": z["lat"], "lon": z["lon"]},
                    "latest_aqi": aqi["aqi"] if aqi else None, "aqi_category": aqi["category"] if aqi else None,
                    "open_alerts": counts["active"] + counts["acknowledged"],
                    "last_data_timestamp": reading_repo.latest_reading_time(db, z["id"])})
    return out


def _water_block(db: Session, zone_id: str, latest: datetime | None) -> dict:
    rules = alert_repo.thresholds_for_zone(db, zone_id)
    params = []
    for p in WATER_PARAMETERS:
        sp = PARAMETERS[p]
        t = arepo.latest_feature_time(db, zone_id, f"{p}_mean")
        val = _f(arepo.latest_features(db, zone_id, [f"{p}_mean"], t).get(f"{p}_mean", {}).get("value")) if t else None
        prules = [r for r in rules if r["parameter"] == p]
        limits = " and ".join(f"{'≤' if r['direction'] == 'above' else '≥'} {r['threshold_value']:g} {sp.unit}"
                              for r in sorted(prules, key=lambda r: r["direction"])) or "no limit configured"
        stale = t is not None and latest is not None and latest - t > timedelta(hours=1)
        params.append({"parameter": p, "label": sp.label, "value": None if stale else val, "unit": sp.unit,
                       "status": "no_data" if stale else water_status(val, prules), "limits": limits,
                       "timestamp": t})
    statuses = {x["status"] for x in params}
    overall = "Outside limits" if "outside_limits" in statuses else \
        ("No data" if statuses == {"no_data"} else "Within limits")
    is_sim = any(x["is_simulated"] for x in sh_repo.list_sources(db) if x["category"] == "water")
    return {"status": overall, "parameters": params, "is_simulated": is_sim,
            "method": "Status classification of each water parameter against the configured limits (no composite "
                      "WQI is computed because no WQI formula is configured). Latest 15-min zone means."}


def summary(db: Session, zone_id: str, window: dict) -> dict:
    zone = require_zone(db, zone_id)
    version = rcache.data_version()
    cache_key = f"cache:summary:{zone_id}:{window['start'].isoformat()}:{window['end'].isoformat()}:{version}"
    if version is not None and (cached := rcache.cache_get(cache_key)):
        return cached
    s, d = get_settings(), bucket_delta()
    latest = reading_repo.latest_reading_time(db, zone_id)
    latest_bucket = floor_bucket(latest) if latest else None
    aqi = arepo.latest_aqi(db, zone_id)
    aqi_fresh = aqi is not None and latest_bucket is not None and latest_bucket - aqi["timestamp"] <= timedelta(hours=1)
    lookback = s.active_anomaly_lookback_buckets
    active_anoms = arepo.count_anomalies(db, zone_id, latest_bucket - (lookback - 1) * d, latest_bucket) \
        if latest_bucket else 0
    counts = alert_repo.count_open(db, zone_id)
    decisions = alert_service.threshold_status(db, zone_id)
    quality = reading_repo.quality_summary(db, zone_id, window["start"], window["end"] + d)
    sources = {x["source_name"]: x for x in sh_repo.list_sources(db)}
    degraded = [n for n, x in sources.items() if x["is_simulated"] and x["status"] in ("DEGRADED", "OFFLINE")]
    anomalies_range = arepo.count_anomalies(db, zone_id, window["start"], window["end"])
    fc_runs = [arepo.latest_forecast_run(db, zone_id, p) for p in AIR_PARAMETERS + WATER_PARAMETERS]
    fc_ok = sum(1 for run in fc_runs if run and run[0]["based_on_until"] == latest_bucket)
    open_alerts = counts["active"] + counts["acknowledged"]
    pending = sum(1 for x in decisions if x["decision"] == "pending_persistence")
    pipeline = [
        {"stage": "collect", "status": "degraded" if degraded else ("ok" if latest else "no_data"),
         "detail": (f"Source outage: {', '.join(degraded)}" if degraded else
                    f"{sum(quality.values())} readings in range")},
        {"stage": "unify", "status": "ok" if latest_bucket else "no_data",
         "detail": f"Aligned to {s.default_time_window_minutes}-min windows" +
                   (f" up to {latest_bucket:%H:%M} UTC" if latest_bucket else "")},
        {"stage": "detect", "status": "attention" if active_anoms else "ok",
         "detail": f"{active_anoms} active anomal{'y' if active_anoms == 1 else 'ies'}; {anomalies_range} in range"},
        {"stage": "explain", "status": "attention" if anomalies_range else "ok",
         "detail": "Likely-contributor estimates available" if anomalies_range else "No anomaly to explain"},
        {"stage": "predict", "status": "ok" if fc_ok else "no_data",
         "detail": f"{fc_ok} of {len(PARAMETERS)} parameter forecasts current"},
        {"stage": "alert", "status": "attention" if open_alerts or pending else "ok",
         "detail": f"{open_alerts} open alert{'s' if open_alerts != 1 else ''}; {pending} rule{'s' if pending != 1 else ''} pending persistence"},
    ]
    result = {
        "zone_id": zone_id, "zone_name": zone["name"], "window": window, "last_updated": latest,
        "aqi": {"value": aqi["aqi"] if aqi_fresh else None, "category": aqi["category"] if aqi_fresh else None,
                "dominant_parameter": aqi["dominant_parameter"] if aqi_fresh else None,
                "timestamp": aqi["timestamp"] if aqi else None, "source": aqi["source"] if aqi else None,
                "method": AQI_METHOD, "status": "OK" if aqi_fresh else "NO_DATA"},
        "water": _water_block(db, zone_id, latest_bucket),
        "active_anomalies": active_anoms,
        "active_anomaly_definition": f"Anomalies in the latest {lookback} windows ({lookback * s.default_time_window_minutes} min) of zone data.",
        "anomalies_in_range": anomalies_range,
        "active_alerts": counts["active"], "acknowledged_alerts": counts["acknowledged"],
        "threshold_decisions": decisions, "data_quality": quality, "pipeline": pipeline,
    }
    if version is not None:
        rcache.cache_set(cache_key, result, ttl=60)
    return result


def map_layers(db: Session, zone_id: str, parameter: str, window: dict) -> dict:
    zone = require_zone(db, zone_id)
    latest_by_sensor: dict[str, list] = {}
    for r in reading_repo.latest_sensor_readings(db, zone_id):
        sp = PARAMETERS[r["parameter"]]
        latest_by_sensor.setdefault(r["sensor_id"], []).append({**r, "label": sp.label})
    sources = {x["source_name"]: x for x in sh_repo.list_sources(db)}
    sensors = [{"id": x["id"], "type": x["type"], "name": x["name"], "lat": x["latitude"], "lon": x["longitude"],
                "source": x["source"], "is_simulated": bool(sources.get(x["source"], {}).get("is_simulated", True)),
                "latest": sorted(latest_by_sensor.get(x["id"], []), key=lambda r: r["parameter"])}
               for x in sensor_repo.zone_sensors(db, zone_id)]
    latest_out = factory_repo.latest_outputs(db, zone_id)
    trend_start = window["end"] - timedelta(hours=24)
    factories = []
    for f in factory_repo.zone_factories(db, zone_id):
        series = factory_repo.output_series(db, f["id"], trend_start, window["end"] + bucket_delta())
        factories.append({**f, "latest_output": latest_out.get(f["id"]),
                          "output_trend": [{"timestamp": p["timestamp"], "value": p["value"]} for p in series]})
    d = bucket_delta()
    events = [{**e, "active_at_latest": e["start_time"] <= window["end"] < (e["end_time"] or window["end"] + d)}
              for e in event_repo.events_overlapping(db, zone_id, window["start"], window["end"] + d)]
    rules = [r for r in alert_repo.thresholds_for_zone(db, zone_id) if r["parameter"] == parameter]
    ref = next((r["threshold_value"] for r in rules if r["direction"] == "above"), None)
    intensity = []
    if ref:
        for s in sensors:
            v = next((r for r in s["latest"] if r["parameter"] == parameter and r["quality_flag"] == "VALID"), None)
            if v and v["value"] is not None:
                intensity.append({"sensor_id": s["id"], "lat": s["lat"], "lon": s["lon"], "value": v["value"],
                                  "unit": PARAMETERS[parameter].unit, "level": round(v["value"] / ref, 3)})
    return {"zone_id": zone_id, "zone": zone, "window": window, "parameter": parameter, "sensors": sensors,
            "factories": factories, "events": events, "intensity": intensity,
            "intensity_note": ("Intensity is drawn only at sensor locations (latest VALID reading ÷ configured "
                               "threshold). No spatial interpolation: sensor density is too low to support it.")}


def trends(db: Session, zone_id: str, parameter: str, window: dict) -> dict:
    require_zone(db, zone_id)
    sp = PARAMETERS[parameter]
    names = [f"{parameter}_mean", f"{parameter}_valid_sensors", f"{parameter}_confidence"]
    frame = grid_frame(db, zone_id, names, window["start"], window["end"])
    series = [{"timestamp": ts, "value": _f(r[names[0]]), "valid_sensors": _f(r[names[1]]),
               "confidence": _f(r[names[2]])} for ts, r in frame.iterrows()]
    factories = factory_repo.zone_factories(db, zone_id)
    fframe = grid_frame(db, zone_id, [f"factory_{f['id']}_output" for f in factories], window["start"], window["end"])
    factory_series = [{"factory_id": f["id"], "name": f["name"], "unit": "%",
                       "points": [{"timestamp": ts, "value": _f(v)} for ts, v in fframe[f"factory_{f['id']}_output"].items()]}
                      for f in factories]
    d = bucket_delta()
    events = event_repo.events_overlapping(db, zone_id, window["start"], window["end"] + d)
    return {"zone_id": zone_id, "parameter": parameter, "label": sp.label, "unit": sp.unit, "window": window,
            "series": series, "missing_windows": sum(1 for x in series if x["value"] is None),
            "factory_series": factory_series,
            "event_markers": [{"id": e["id"], "type": e["type"], "start_time": e["start_time"],
                               "end_time": e["end_time"], "severity": e["severity"], "description": e["description"]}
                              for e in events],
            "quality_counts": reading_repo.quality_summary(db, zone_id, window["start"], window["end"] + d),
            "source_label": _source_label(db, parameter)}


def anomaly_view(db: Session, zone_id: str, parameter: str, window: dict) -> dict:
    require_zone(db, zone_id)
    s, sp = get_settings(), PARAMETERS[parameter]
    k = s.anomaly_zscore_threshold
    names = [f"{parameter}_mean", f"{parameter}_rolling_mean", f"{parameter}_rolling_std", f"{parameter}_deviation"]
    frame = grid_frame(db, zone_id, names, window["start"], window["end"])
    series = []
    for ts, r in frame.iterrows():
        mean, std = _f(r[names[1]]), _f(r[names[2]])
        series.append({"timestamp": ts, "value": _f(r[names[0]]), "rolling_mean": mean,
                       "baseline_low": mean - k * std if mean is not None and std is not None else None,
                       "baseline_high": mean + k * std if mean is not None and std is not None else None,
                       "score": _f(r[names[3]])})
    anomalies = arepo.list_anomalies(db, zone_id, parameter, window["start"], window["end"])
    has_values = any(x["value"] is not None for x in series)
    has_baseline = any(x["rolling_mean"] is not None for x in series)
    status = "NO_DATA" if not has_values else ("OK" if has_baseline else "INSUFFICIENT_HISTORY")
    return {"zone_id": zone_id, "parameter": parameter, "label": sp.label, "unit": sp.unit, "window": window,
            "status": status,
            "detector": {"method": "rolling mean ± k·rolling std (anomalous windows excluded from the baseline)",
                         "version": s.detector_version, "k": k, "baseline_windows": s.baseline_window_buckets,
                         "min_baseline_windows": s.min_baseline_buckets},
            "series": series, "anomalies": anomalies,
            "note": "An anomaly is unusual relative to the zone's own baseline. It is not a threshold breach; "
                    "alerts are decided separately by the threshold engine."}


def forecast_history(db: Session, zone_id: str, parameter: str, window: dict) -> list[dict]:
    frame = grid_frame(db, zone_id, [f"{parameter}_mean"], window["start"], window["end"])
    return [{"timestamp": ts, "value": _f(v)} for ts, v in frame[f"{parameter}_mean"].items()]


def source_health(db: Session) -> dict:
    rows = sh_repo.list_sources(db)
    counts: dict[str, int] = {}
    out = []
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        out.append({**r, "latency_ms": r["latency"], "last_known_good": rcache.cache_get(f"lkg:{r['source_name']}")})
    return {"sources": out, "counts": counts}


def _source_label(db: Session, parameter: str) -> str:
    """Honest provenance label for a parameter's data: SIMULATED if any simulated source feeds that domain."""
    domain = PARAMETERS[parameter].domain
    sim = [x for x in sh_repo.list_sources(db) if x["category"] == domain and x["is_simulated"]]
    return "SIMULATED DEMO STREAM" if sim else "Live source"
