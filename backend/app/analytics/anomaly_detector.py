"""Rolling-baseline anomaly detector (primary method of the spec).

For each window t: baseline = mean/std of the previous `window` windows, EXCLUDING windows already
flagged anomalous (so a sustained spike is not absorbed into its own baseline) and missing values.
Band = mean ± k·std; score = z = (x − mean) / std; |z| > k -> anomaly.
Fallback: if fewer than `min_n` unflagged windows remain but at least `min_n` observed windows exist,
the baseline re-includes flagged windows (a sustained level shift becomes the new normal); noted per row.
The detector knows nothing about regulatory thresholds: anomaly != threshold breach."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

ABS_STD_FLOOR = {"pm25": 1.0, "pm10": 1.5, "no2": 1.0, "ph": 0.03, "turbidity": 0.3, "dissolved_oxygen": 0.08}


@dataclass
class DetectorConfig:
    window: int = 96
    min_n: int = 24
    k: float = 3.0


def std_floor(param: str, mean: float) -> float:
    return max(ABS_STD_FLOOR.get(param, 0.01), 0.02 * abs(mean))


def detect(series: pd.Series, param: str, start_pos: int, prior_flags: np.ndarray | None,
           cfg: DetectorConfig) -> pd.DataFrame:
    """`series` must lie on a complete regular window grid (NaN where missing). Rows from `start_pos`
    on are evaluated; flags before `start_pos` come from `prior_flags` (previously stored results)."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    flags = np.zeros(n, dtype=bool)
    if prior_flags is not None:
        flags[:start_pos] = prior_flags[:start_pos]
    out = []
    for i in range(start_pos, n):
        v = values[i]
        lo = max(0, i - cfg.window)
        hist, hist_flags = values[lo:i], flags[lo:i]
        observed = ~np.isnan(hist)
        clean = hist[observed & ~hist_flags]
        note = None
        if len(clean) < cfg.min_n and observed.sum() >= cfg.min_n:
            clean, note = hist[observed], "baseline re-includes flagged windows (sustained level shift)"
        prev = values[i - 1] if i > 0 else np.nan
        roc = float(v - prev) if not (np.isnan(v) or np.isnan(prev)) else None
        row = {"timestamp": series.index[i], "value": None if np.isnan(v) else float(v), "rolling_mean": None,
               "rolling_std": None, "baseline_low": None, "baseline_high": None, "z": None, "is_anomaly": False,
               "rate_of_change": roc, "n_baseline": int(len(clean)), "status": "ok", "note": note}
        if len(clean) < cfg.min_n:
            row["status"] = "insufficient_history"
        else:
            mean = float(np.mean(clean))
            std = max(float(np.std(clean, ddof=1)), std_floor(param, mean))
            row.update(rolling_mean=mean, rolling_std=std, baseline_low=mean - cfg.k * std,
                       baseline_high=mean + cfg.k * std)
            if np.isnan(v):
                row["status"] = "missing"
            else:
                z = (v - mean) / std
                row["z"] = float(z)
                if abs(z) > cfg.k:
                    row["is_anomaly"] = True
                    flags[i] = True
        out.append(row)
    return pd.DataFrame(out)
