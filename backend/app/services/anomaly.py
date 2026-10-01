"""Anomaly service: runs the rolling-baseline detector for a zone/parameter over a range of windows,
persists rolling features, and upserts anomaly records (idempotent; re-runs give identical results)."""
import logging
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.analytics.anomaly_detector import DetectorConfig, detect
from app.core.config import get_settings
from app.core.logging import log
from app.core.parameters import PARAMETERS
from app.core.timeutil import bucket_delta, floor_bucket
from app.repositories import analytics as arepo
from app.services.features import grid_series, rolling_feature_rows

logger = logging.getLogger("enviropulse.anomaly")


def detector_config() -> DetectorConfig:
    s = get_settings()
    return DetectorConfig(window=s.baseline_window_buckets, min_n=s.min_baseline_buckets, k=s.anomaly_zscore_threshold)


def reason_text(param: str, value: float, z: float, mean: float, low: float, high: float, n: int, k: float) -> str:
    sp = PARAMETERS[param]
    direction = "above" if z > 0 else "below"
    return (f"{sp.label} zone mean {value:.2f} {sp.unit} is {abs(z):.1f}σ {direction} its rolling baseline "
            f"(mean {mean:.2f} {sp.unit}; normal band {low:.2f}–{high:.2f} at ±{k:g}σ; {n} baseline windows). "
            f"This is a statistical deviation, not a threshold decision.")


def run_anomaly_detection(db: Session, zone_id: str, param: str, start: datetime, end: datetime) -> list[int]:
    s, cfg, d = get_settings(), detector_config(), bucket_delta()
    start, end = floor_bucket(start), floor_bucket(end)
    load_start = start - cfg.window * d
    series = grid_series(db, zone_id, f"{param}_mean", load_start, end)
    start_pos = int(series.index.get_indexer([start])[0])
    prior = arepo.anomaly_timestamps(db, zone_id, param, load_start, start, s.detector_version)
    prior_flags = np.array([ts in prior for ts in series.index], dtype=bool)
    result = detect(series, param, start_pos, prior_flags, cfg)
    arepo.upsert_features(db, rolling_feature_rows(zone_id, param, result))

    new_ids, keep = [], []
    for r in result[result["is_anomaly"]].itertuples(index=False):
        keep.append(r.timestamp)
        aid, inserted = arepo.upsert_anomaly(db, {
            "zone_id": zone_id, "timestamp": r.timestamp, "parameter": param, "value": r.value, "score": r.z,
            "direction": "high" if r.z > 0 else "low", "baseline_mean": r.rolling_mean,
            "baseline_low": r.baseline_low, "baseline_high": r.baseline_high,
            "reason": reason_text(param, r.value, r.z, r.rolling_mean, r.baseline_low, r.baseline_high,
                                  r.n_baseline, cfg.k) + (f" Note: {r.note}." if r.note else ""),
            "detector_version": s.detector_version})
        if inserted:
            new_ids.append(aid)
    arepo.delete_anomalies_not_in(db, zone_id, param, start, end, keep, s.detector_version)
    if new_ids:
        log(logger, logging.INFO, "anomalies detected", zone=zone_id, parameter=param, count=len(new_ids))
    return new_ids
