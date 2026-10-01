from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common import ZONE_ERRORS, WindowParams, parameter_query, raise_http
from app.api.routes_zones import ZoneId
from app.core.dependencies import get_db
from app.models.schemas import AnomaliesResponse, AttributionResponse, ForecastResponse, ParameterKey
from app.services import attribution as attribution_service
from app.services import dashboard
from app.services import forecast as forecast_service

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/zones/{zone_id}/anomalies", response_model=AnomaliesResponse, responses=ZONE_ERRORS,
            summary="Anomaly timeline: observed series, rolling baseline band and anomaly points")
def zone_anomalies(zone_id: str = ZoneId, parameter: ParameterKey = parameter_query(), w: WindowParams = Depends(),
                   db: Session = Depends(get_db)):
    """Returns status INSUFFICIENT_HISTORY when no baseline can be formed yet (controlled state)."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        return dashboard.anomaly_view(db, zone_id, parameter, window)
    except Exception as exc:
        raise_http(exc)


@router.get("/zones/{zone_id}/attribution", response_model=AttributionResponse, responses=ZONE_ERRORS,
            summary="Source-attribution ESTIMATE for an anomaly (likely contributors)")
def zone_attribution(zone_id: str = ZoneId, parameter: ParameterKey | None = Query(None),
                     anomaly_id: int | None = Query(None, ge=1, description="Explain a specific anomaly; default: latest in range"),
                     w: WindowParams = Depends(), db: Session = Depends(get_db)):
    """Ranked likely contributors with score, evidence, aligned time window and data quality, plus
    factory-vs-pollutant scatter data. Association only — never proof of causation.
    Status NO_ANOMALY_IN_RANGE when there is nothing to explain."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        dashboard.require_zone(db, zone_id)
        return attribution_service.attribution_view(db, zone_id, parameter, anomaly_id, window["start"], window["end"])
    except Exception as exc:
        raise_http(exc)


@router.get("/zones/{zone_id}/forecast", response_model=ForecastResponse, responses=ZONE_ERRORS,
            summary="Next-window forecast with prediction band and validation metrics")
def zone_forecast(zone_id: str = ZoneId, parameter: ParameterKey = parameter_query(), w: WindowParams = Depends(),
                  db: Session = Depends(get_db)):
    """Model chosen by held-out RMSE; returns MAE/RMSE, band and risk vs threshold. Controlled statuses:
    INSUFFICIENT_HISTORY, INSUFFICIENT_RECENT_DATA, MODEL_ERROR (no fabricated forecast)."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        dashboard.require_zone(db, zone_id)
        result = forecast_service.get_forecast(db, zone_id, parameter)
        result["history"] = dashboard.forecast_history(db, zone_id, parameter, window)
        return result
    except Exception as exc:
        raise_http(exc)
