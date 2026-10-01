"""Feature layer helpers: regular-grid series loading and persistence of derived rolling features
(rolling mean, rolling std, deviation from baseline, rate of change). Every feature row carries an
explicit name, value, unit, timestamp and source-window description."""
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.parameters import PARAMETERS
from app.repositories import analytics as arepo
from app.services.alignment import bucket_grid


def grid_series(db: Session, zone_id: str, name: str, start: datetime, end: datetime) -> pd.Series:
    """Feature as a series on the complete window grid [start, end] (NaN where nothing was observed)."""
    frame = arepo.feature_frame(db, zone_id, [name], start, end)
    idx = pd.DatetimeIndex(bucket_grid(start, end))
    if frame.empty:
        return pd.Series(index=idx, dtype=float, name=name)
    return frame[name].reindex(idx).astype(float)


def grid_frame(db: Session, zone_id: str, names: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    frame = arepo.feature_frame(db, zone_id, names, start, end)
    return frame.reindex(pd.DatetimeIndex(bucket_grid(start, end))).astype(float)


def rolling_feature_rows(zone_id: str, param: str, detected: pd.DataFrame) -> list[dict]:
    s = get_settings()
    unit = PARAMETERS[param].unit
    win = f"previous {s.baseline_window_buckets} windows excluding flagged anomalies"
    rows = []
    for r in detected.itertuples(index=False):
        for name, value, u, src in (
            (f"{param}_rolling_mean", r.rolling_mean, unit, win),
            (f"{param}_rolling_std", r.rolling_std, unit, win),
            (f"{param}_deviation", r.z, "z-score", f"(value − rolling mean) / rolling std; {win}"),
            (f"{param}_rate_of_change", r.rate_of_change, f"{unit} per window", "difference from previous window"),
        ):
            rows.append({"zone_id": zone_id, "timestamp": r.timestamp, "feature_name": name,
                         "value": None if value is None or pd.isna(value) else float(value), "unit": u,
                         "source_window": src})
    return rows
