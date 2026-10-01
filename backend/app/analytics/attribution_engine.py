"""Source-attribution ESTIMATE (association, not causation).

For an anomaly at window t, over the aligned window [t − W, t]:
  * lagged Pearson correlation between the pollutant and each candidate at lags 0..2 windows
    (the best positive lag is kept),
  * candidate deviation during the anomaly: how unusual the candidate was in the last `recent` windows
    relative to its own earlier behaviour within the same analysis window,
  * score = 0.5·clip(r, 0, 1) + 0.5·clip(deviation, 0, 1)   (deviation = z/3 for continuous signals;
    1 for an event that newly became active; else 0).
The score ranks *likely contributors*. It is an association heuristic and never proof of cause."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

METHOD = ("Lagged Pearson association (lags 0–2 windows) combined with each candidate's deviation during the "
          "anomaly window. Association only — not proof of causation.")


@dataclass
class Candidate:
    type: str          # factory | event
    id: str
    name: str
    series: pd.Series  # on the same regular grid as the target
    kind: str          # continuous | binary
    unit: str


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def rank_contributors(target: pd.Series, candidates: list[Candidate], lags=(0, 1, 2), recent: int = 3,
                      min_pairs: int = 24) -> list[dict]:
    results = []
    y_all = target.to_numpy(dtype=float)
    target_missing = float(np.isnan(y_all).mean()) if len(y_all) else 1.0
    for c in candidates:
        best = None
        for lag in lags:
            x_all = c.series.shift(lag).to_numpy(dtype=float)
            mask = ~np.isnan(x_all) & ~np.isnan(y_all)
            n = int(mask.sum())
            if n < min_pairs:
                continue
            r = _pearson(x_all[mask], y_all[mask])
            if r is not None and (best is None or r > best[1]):
                best = (lag, r, n)
        lag = best[0] if best else 0
        x = c.series.shift(lag).to_numpy(dtype=float)
        recent_vals = x[-recent:][~np.isnan(x[-recent:])]
        base_vals = x[:-recent][~np.isnan(x[:-recent])]
        deviation, dev_norm, dev_text = None, 0.0, "no data during the anomaly window"
        if c.kind == "continuous" and len(recent_vals) and len(base_vals) >= 3:
            bm, bs = float(np.mean(base_vals)), max(float(np.std(base_vals, ddof=1)), 1.0)
            rm = float(np.mean(recent_vals))
            deviation = (rm - bm) / bs
            dev_norm = float(np.clip(deviation / 3.0, 0, 1))
            dev_text = f"{rm:.1f}{c.unit} during the anomaly vs {bm:.1f} ± {bs:.1f}{c.unit} earlier ({deviation:+.1f}σ)"
        elif c.kind == "binary":
            raw = c.series.to_numpy(dtype=float)
            active_recent = bool(np.nansum(raw[-recent:]) > 0)
            base_active = float(np.nanmean(raw[:-recent])) if len(raw) > recent else 0.0
            deviation = 1.0 if active_recent and base_active < 0.5 else 0.0
            dev_norm = deviation
            dev_text = ("active during the anomaly window" if active_recent else "not active during the anomaly window") \
                + f" (active in {base_active * 100:.0f}% of earlier windows)"
        r_val = best[1] if best else None
        score = 0.5 * float(np.clip(r_val or 0.0, 0, 1)) + 0.5 * dev_norm
        if score <= 0.05:
            continue
        corr_text = (f"association r = {r_val:.2f} at lag t-{lag} over {best[2]} aligned windows" if best
                     else "correlation unavailable (insufficient variation or overlap)")
        cand_missing = float(np.isnan(c.series.to_numpy(dtype=float)).mean()) if len(c.series) else 1.0
        results.append({
            "contributor_type": c.type, "contributor_id": c.id, "contributor_name": c.name,
            "score": round(score, 4), "correlation": None if r_val is None else round(r_val, 4),
            "best_lag_windows": lag if best else None, "deviation": None if deviation is None else round(deviation, 3),
            "evidence": f"{dev_text}; {corr_text}.",
            "data_quality": {"aligned_windows": best[2] if best else 0,
                             "target_missing_fraction": round(target_missing, 3),
                             "candidate_missing_fraction": round(cand_missing, 3)},
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results
