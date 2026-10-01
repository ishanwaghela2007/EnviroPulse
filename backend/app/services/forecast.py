"""Forecast service: reuse the stored run if it is based on the latest window, otherwise train/validate
and store a new run. Controlled states: INSUFFICIENT_HISTORY, INSUFFICIENT_RECENT_DATA, MODEL_ERROR."""
import logging
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.analytics.forecast_engine import forecast as run_forecast
from app.core.config import get_settings
from app.core.logging import log
from app.core.parameters import PARAMETERS
from app.core.timeutil import bucket_delta, utcnow
from app.repositories import alerts as alert_repo
from app.repositories import analytics as arepo
from app.services.features import grid_series

logger = logging.getLogger("enviropulse.forecast")
TRAINING_DAYS = 14


def _risk(param: str, preds: list[dict], rules: list[dict]) -> dict:
    sp = PARAMETERS[param]
    rules = [r for r in rules if r["parameter"] == param]
    if not rules:
        return {"level": "no_threshold", "message": f"No threshold is configured for {sp.label}."}
    for r in rules:
        above = r["direction"] == "above"
        thr = r["threshold_value"]
        for p in preds:
            central = p["prediction"] > thr if above else p["prediction"] < thr
            if central:
                return {"level": "breach_predicted", "threshold": thr, "direction": r["direction"],
                        "first_time": p["target_time"],
                        "message": f"Predicted {sp.label} crosses the {thr:g} {sp.unit} threshold "
                                   f"({r['direction']}) within the forecast horizon."}
        for p in preds:
            band = p["upper_bound"] > thr if above else p["lower_bound"] < thr
            if band:
                return {"level": "possible_breach", "threshold": thr, "direction": r["direction"],
                        "first_time": p["target_time"],
                        "message": f"The uncertainty band reaches the {thr:g} {sp.unit} threshold; a breach is possible."}
    return {"level": "below_threshold", "message": f"Forecast and band stay within configured {sp.label} limits."}


def get_forecast(db: Session, zone_id: str, param: str) -> dict:
    s, d = get_settings(), bucket_delta()
    sp = PARAMETERS[param]
    base = {"zone_id": zone_id, "parameter": param, "unit": sp.unit, "label": sp.label,
            "horizon_windows": s.forecast_horizon, "window_minutes": s.default_time_window_minutes}
    latest = arepo.latest_feature_time(db, zone_id, f"{param}_mean")
    if latest is None:
        return {**base, "status": "INSUFFICIENT_HISTORY", "message": "No observations for this zone and parameter.",
                "points": []}
    rules = alert_repo.thresholds_for_zone(db, zone_id)
    stored = arepo.latest_forecast_run(db, zone_id, param)
    if stored and stored[0]["based_on_until"] == latest and stored[0]["model_version"] == s.model_version:
        preds = [{k: r[k] for k in ("target_time", "prediction", "lower_bound", "upper_bound")} for r in stored]
        return {**base, "status": "OK", "model": stored[0]["model"], "model_version": s.model_version,
                "generated_at": stored[0]["generated_at"], "based_on_until": latest, "run_id": stored[0]["run_id"],
                "validation": stored[0]["validation_metadata"], "points": preds, "risk": _risk(param, preds, rules),
                "cached": True}
    series = grid_series(db, zone_id, f"{param}_mean", latest - timedelta(days=TRAINING_DAYS) + d, latest)
    try:
        result = run_forecast(series, s.forecast_horizon, s.forecast_min_history_buckets, d, sp.physical_range)
    except Exception as exc:  # controlled fallback: the dashboard stays usable
        log(logger, logging.ERROR, "forecast model failure", zone=zone_id, parameter=param, error=str(exc))
        return {**base, "status": "MODEL_ERROR", "message": "The forecast model failed; no forecast is shown.",
                "points": []}
    if result["status"] != "OK":
        return {**base, **result, "points": []}
    run_id, now = uuid.uuid4().hex[:16], utcnow()
    arepo.insert_forecast_rows(db, [{
        "run_id": run_id, "zone_id": zone_id, "parameter": param, "generated_at": now, "based_on_until": latest,
        "target_time": p["target_time"], "prediction": p["prediction"], "lower_bound": p["lower_bound"],
        "upper_bound": p["upper_bound"], "model": result["model"], "model_version": s.model_version,
        "validation_metadata": result["validation"]} for p in result["predictions"]])
    log(logger, logging.INFO, "forecast generated", zone=zone_id, parameter=param, model=result["model"],
        rmse=result["validation"]["rmse"])
    return {**base, "status": "OK", "model": result["model"], "model_version": s.model_version, "generated_at": now,
            "based_on_until": latest, "run_id": run_id, "validation": result["validation"],
            "points": result["predictions"], "risk": _risk(param, result["predictions"], rules), "cached": False}
