"""Next-window forecast with held-out validation.

Candidate models (the simplest that validates best wins, chosen by held-out RMSE):
  * persistence        : x(t+1) = x(t)
  * seasonal_naive_24h : x(t+1) = x(t+1−96)
  * ridge_lag          : Ridge regression on lags 1,2,3,4,96 + hour-of-day sin/cos (scikit-learn)
Validation: chronological split, last 20 % (min 48 windows) held out, one-step-ahead MAE / RMSE.
Multi-step forecasts are recursive. Prediction band = ±1.96·RMSE_holdout·√h (an approximation that
assumes roughly independent one-step errors — documented as approximate).
Gap policy: gaps ≤ 2 windows are linearly interpolated for model input only; longer gaps stay missing
and those rows are excluded from training."""
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.analytics.metrics import mae, rmse

LAGS = [1, 2, 3, 4, 96]
Z = 1.96


def _features(s: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({f"lag{l}": s.shift(l) for l in LAGS}, index=s.index)
    hours = s.index.hour + s.index.minute / 60.0
    df["hour_sin"] = np.sin(2 * np.pi * hours / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hours / 24)
    return df


def forecast(series: pd.Series, horizon: int, min_history: int, step: timedelta,
             value_range: tuple[float, float]) -> dict:
    observed = int(series.notna().sum())
    if observed < min_history:
        return {"status": "INSUFFICIENT_HISTORY", "observed_windows": observed, "required_windows": min_history,
                "message": f"A forecast needs at least {min_history} observed windows; {observed} are available."}
    if series.iloc[-4:].notna().sum() == 0:
        return {"status": "INSUFFICIENT_RECENT_DATA", "observed_windows": observed, "required_windows": min_history,
                "message": "No observation in the last 4 windows, so a forecast would not be anchored to current data."}
    s = series.interpolate(limit=2, limit_area="inside").ffill(limit=2)
    data = _features(s).assign(y=s).dropna()
    n = len(data)
    n_test = max(48, int(n * 0.2))
    if n - n_test < 96:
        return {"status": "INSUFFICIENT_HISTORY", "observed_windows": observed, "required_windows": min_history,
                "message": "Not enough complete lag rows to train and hold out a validation period."}
    train, test = data.iloc[:-n_test], data.iloc[-n_test:]
    feats = [c for c in data.columns if c != "y"]
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(train[feats], train["y"])
    preds = {"persistence": test["lag1"].to_numpy(), "seasonal_naive_24h": test["lag96"].to_numpy(),
             "ridge_lag": ridge.predict(test[feats])}
    y_test = test["y"].to_numpy()
    scores = {k: {"mae": mae(y_test, v), "rmse": rmse(y_test, v)} for k, v in preds.items()}
    chosen = min(scores, key=lambda k: scores[k]["rmse"])
    err = scores[chosen]["rmse"]

    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(data[feats], data["y"]) if chosen == "ridge_lag" else None
    ext = s.copy()
    lo_clip, hi_clip = value_range
    last_ts = s.index[-1]
    out = []
    for h in range(1, horizon + 1):
        ts = last_ts + h * step
        ext.loc[ts] = np.nan
        if chosen == "persistence":
            yhat = float(ext.iloc[-2])
        elif chosen == "seasonal_naive_24h":
            yhat = float(ext.iloc[-97])
        else:
            yhat = float(model.predict(_features(ext).iloc[[-1]][feats])[0])
        ext.loc[ts] = yhat
        band = Z * err * np.sqrt(h)
        out.append({"target_time": ts, "prediction": float(np.clip(yhat, lo_clip, hi_clip)),
                    "lower_bound": float(np.clip(yhat - band, lo_clip, hi_clip)),
                    "upper_bound": float(np.clip(yhat + band, lo_clip, hi_clip))})
    return {
        "status": "OK", "model": chosen, "predictions": out, "based_on_until": last_ts,
        "validation": {
            "method": "chronological hold-out, one-step-ahead", "train_windows": int(len(train)),
            "holdout_windows": int(n_test), "train_period": [train.index[0], train.index[-1]],
            "holdout_period": [test.index[0], test.index[-1]], "selected_model": chosen,
            "mae": round(scores[chosen]["mae"], 4), "rmse": round(err, 4),
            "candidates": {k: {"mae": round(v["mae"], 4), "rmse": round(v["rmse"], 4)} for k, v in scores.items()},
            "band": "±1.96·RMSE_holdout·√h (approximate)",
            "gap_policy": "gaps ≤ 2 windows interpolated for model input only",
        },
    }
