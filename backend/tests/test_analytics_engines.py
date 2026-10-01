"""Pure analytics engines on synthetic series with known answers."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.analytics import metrics
from app.analytics.anomaly_detector import DetectorConfig, detect
from app.analytics.attribution_engine import Candidate, rank_contributors
from app.analytics.forecast_engine import forecast

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)


def grid(n):
    return pd.DatetimeIndex([T0 + i * STEP for i in range(n)])


def test_detector_flags_spike_with_band_and_reason_fields():
    rng = np.random.default_rng(1)
    s = pd.Series(40 + rng.normal(0, 2, 200), index=grid(200))
    s.iloc[150] = 80
    out = detect(s, "pm25", 0, None, DetectorConfig())
    row = out.iloc[150]
    assert row.is_anomaly and row.z > 3 and row.baseline_low < 40 < row.baseline_high
    assert out.iloc[:24].status.eq("insufficient_history").all()
    # the spike must not distort the following windows (pure-noise ±3σ exceedances elsewhere are expected ~0.3%)
    assert out.iloc[151:165].is_anomaly.sum() == 0
    assert abs(out.iloc[151].rolling_mean - out.iloc[149].rolling_mean) < 1.0  # spike excluded from baseline


def test_detector_sustained_spike_stays_anomalous_and_missing_not_zero():
    rng = np.random.default_rng(2)
    s = pd.Series(40 + rng.normal(0, 2, 200), index=grid(200))
    s.iloc[150:156] = 85
    s.iloc[160] = np.nan
    out = detect(s, "pm25", 0, None, DetectorConfig())
    assert out.iloc[150:156].is_anomaly.all()          # baseline excludes flagged windows
    assert out.iloc[160].status == "missing" and not out.iloc[160].is_anomaly


def test_threshold_crossing_alone_is_not_an_anomaly():
    # a steady series sitting above a regulatory limit (e.g. 60) is NOT anomalous
    rng = np.random.default_rng(3)
    s = pd.Series(70 + rng.normal(0, 1.5, 150), index=grid(150))
    assert detect(s, "pm25", 0, None, DetectorConfig()).is_anomaly.sum() == 0


def test_attribution_recovers_lagged_relationship_and_ranks_it_first():
    rng = np.random.default_rng(4)
    n = 97
    driver = pd.Series(60 + rng.normal(0, 3, n), index=grid(n))
    driver.iloc[-4:] = 95
    noise_factory = pd.Series(50 + rng.normal(0, 3, n), index=grid(n))
    y = 40 + 1.2 * (driver.shift(1).fillna(60) - 60) + rng.normal(0, 1, n)
    event = pd.Series(0.0, index=grid(n))
    ranked = rank_contributors(y, [Candidate("factory", "f1", "Driver", driver, "continuous", "%"),
                                   Candidate("factory", "f2", "Unrelated", noise_factory, "continuous", "%"),
                                   Candidate("event", "e1", "Idle event", event, "binary", "")])
    assert ranked[0]["contributor_id"] == "f1" and ranked[0]["best_lag_windows"] == 1
    assert ranked[0]["correlation"] > 0.8 and "association" in ranked[0]["evidence"]
    assert all(r["contributor_id"] != "e1" for r in ranked)  # no variation -> no fabricated score


def test_forecast_insufficient_history_is_controlled():
    s = pd.Series(np.arange(100.0), index=grid(100))
    r = forecast(s, 8, 288, STEP, (0, 1000))
    assert r["status"] == "INSUFFICIENT_HISTORY" and "predictions" not in r


def test_forecast_returns_validated_prediction_band():
    idx = grid(600)
    hours = idx.hour + idx.minute / 60
    rng = np.random.default_rng(5)
    s = pd.Series(40 + 8 * np.sin(2 * np.pi * hours / 24) + rng.normal(0, 1, 600), index=idx)
    r = forecast(s, 8, 288, STEP, (0, 1000))
    assert r["status"] == "OK" and len(r["predictions"]) == 8
    v = r["validation"]
    assert v["selected_model"] in v["candidates"] and v["rmse"] == min(c["rmse"] for c in v["candidates"].values())
    widths = [p["upper_bound"] - p["lower_bound"] for p in r["predictions"]]
    assert all(w > 0 for w in widths) and widths[-1] > widths[0]  # uncertainty grows with horizon
    assert r["predictions"][0]["target_time"] == idx[-1] + STEP


def test_naqi_indicative_aqi():
    assert metrics.naqi_subindex("pm25", 30) == 50
    assert metrics.naqi_subindex("pm25", 60) == 100
    aqi, cat, dom = metrics.indicative_aqi({"pm25": 75, "pm10": 80, "no2": 30})
    assert (cat, dom) == ("Moderate", "pm25") and 101 <= aqi <= 200
    assert metrics.indicative_aqi({"no2": 30}) == (None, None, None)  # needs a particulate pollutant
