"""Geo-time alignment. Zone assignment already happened at ingestion (PostGIS). Here every source is
bucketed into the configured window, sensors are aggregated per zone, factory output and events are
joined to the same zone/window, and lag features t-1, t-2 are generated.
Output: rows in `features` (explicit name, value, unit, timestamp, source window) + `aqi_snapshots`."""
import logging
import math
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.metrics import AQI_METHOD, indicative_aqi
from app.core.logging import log
from app.core.parameters import AIR_PARAMETERS, EVENT_TYPES, PARAMETERS
from app.core.timeutil import bucket_delta, bucket_minutes, floor_bucket
from app.repositories import analytics as arepo
from app.repositories import events as event_repo
from app.repositories import factories as factory_repo
from app.repositories import readings as reading_repo
from app.repositories import sensors as sensor_repo

logger = logging.getLogger("enviropulse.alignment")
LAGS = (1, 2)


def _clean(v):
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else v


def bucket_grid(start: datetime, end: datetime) -> list[datetime]:
    d = bucket_delta()
    out, t = [], floor_bucket(start)
    while t <= end:
        out.append(t)
        t += d
    return out


def align_zone(db: Session, zone_id: str, start: datetime, end: datetime) -> dict:
    d, m = bucket_delta(), bucket_minutes()
    start, end = floor_bucket(start), floor_bucket(end)
    grid = bucket_grid(start, end)
    window = f"{m}-min window"
    rows: list[dict] = []

    def feat(ts, name, value, unit, src):
        rows.append({"zone_id": zone_id, "timestamp": ts, "feature_name": name, "value": _clean(value), "unit": unit,
                     "source_window": src})

    # 1) readings -> zone window means (VALID only) + data confidence
    expected = sensor_repo.expected_sensor_counts(db, zone_id)
    for a in reading_repo.zone_bucket_aggregates(db, zone_id, start, end + d, m):
        p = a["parameter"]
        feat(a["bucket"], f"{p}_mean", a["mean"], PARAMETERS[p].unit, f"{window} mean of VALID sensor readings")
        feat(a["bucket"], f"{p}_valid_sensors", a["valid_sensors"], "count", window)
        exp = expected.get(p) or 0
        feat(a["bucket"], f"{p}_confidence", (a["valid_sensors"] / exp) if exp else None, "ratio",
             f"{window}: valid sensors / active sensors")

    # 2) factory output joined to the same windows, with lag features
    by_factory: dict[str, dict[datetime, float]] = {}
    for o in factory_repo.bucket_outputs(db, zone_id, start - d * max(LAGS), end + d, m):
        by_factory.setdefault(o["factory_id"], {})[o["bucket"]] = o["value"]
    for ts in grid:
        totals = {lag: 0.0 for lag in (0, *LAGS)}
        complete = {lag: bool(by_factory) for lag in (0, *LAGS)}
        for fid, series in by_factory.items():
            for lag in (0, *LAGS):
                v = series.get(ts - lag * d)
                suffix = f"_lag{lag}" if lag else ""
                feat(ts, f"factory_{fid}_output{suffix}", v, "%",
                     f"{window} mean production level" + (f" at t-{lag}" if lag else ""))
                if v is None:
                    complete[lag] = False
                else:
                    totals[lag] += v
        for lag in (0, *LAGS):
            suffix = f"_lag{lag}" if lag else ""
            feat(ts, f"factory_output_total{suffix}", totals[lag] if complete[lag] else None, "% (sum)",
                 "sum of zone factory production levels" + (f" at t-{lag}" if lag else ""))

    # 3) local events joined by zone + time overlap
    events = event_repo.events_overlapping(db, zone_id, start, end + d)
    for ts in grid:
        active = {e["type"] for e in events if e["start_time"] < ts + d and (e["end_time"] is None or e["end_time"] > ts)}
        for et in EVENT_TYPES:
            feat(ts, f"event_{et}_active", 1.0 if et in active else 0.0, "flag", f"event overlaps {window}")
        feat(ts, "event_active_any", 1.0 if active else 0.0, "flag", f"any event overlaps {window}")

    arepo.upsert_features(db, rows)

    # 4) indicative AQI from 1-h rolling means (uses the 3 previous windows)
    frame = arepo.feature_frame(db, zone_id, [f"{p}_mean" for p in AIR_PARAMETERS], start - 3 * d, end)
    aqi_rows, aqi_feats = [], []
    if not frame.empty:
        full = frame.reindex(pd.DatetimeIndex(bucket_grid(start - 3 * d, end)))
        hourly = full.rolling(4, min_periods=2).mean()
        for ts in grid:
            concs = {p: _clean(hourly.at[ts, f"{p}_mean"]) for p in AIR_PARAMETERS}
            aqi, cat, dom = indicative_aqi(concs)
            if aqi is None:
                continue
            aqi_rows.append({"zone_id": zone_id, "timestamp": ts, "aqi": aqi, "category": cat,
                             "dominant_parameter": dom, "source": "computed:naqi-indicative", "method": AQI_METHOD})
            aqi_feats.append({"zone_id": zone_id, "timestamp": ts, "feature_name": "aqi_indicative", "value": float(aqi),
                              "unit": "index", "source_window": "1-h rolling mean, max NAQI sub-index"})
    arepo.upsert_aqi(db, aqi_rows)
    arepo.upsert_features(db, aqi_feats)
    log(logger, logging.INFO, "alignment job complete", zone=zone_id, start=start, end=end,
        features=len(rows) + len(aqi_feats), windows=len(grid))
    return {"windows": len(grid), "features": len(rows) + len(aqi_feats)}
