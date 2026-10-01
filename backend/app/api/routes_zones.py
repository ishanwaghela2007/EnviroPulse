from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.common import ZONE_ERRORS, WindowParams, parameter_query, raise_http
from app.core.dependencies import get_db
from app.models.schemas import MapResponse, ParameterKey, SummaryResponse, TrendResponse, ZonesResponse
from app.services import dashboard

router = APIRouter(prefix="/api/v1", tags=["zones"])
ZoneId = Path(..., min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$", description="Zone id, e.g. zone_a")


@router.get("/zones", response_model=ZonesResponse, summary="List industrial zones")
def list_zones(db: Session = Depends(get_db)):
    """All zones with GeoJSON boundary, centroid, latest indicative AQI and open-alert count."""
    return {"zones": dashboard.list_zones(db)}


@router.get("/zones/{zone_id}/summary", response_model=SummaryResponse, responses=ZONE_ERRORS,
            summary="Current zone state (KPIs, threshold decisions, pipeline stages)")
def zone_summary(zone_id: str = ZoneId, w: WindowParams = Depends(), db: Session = Depends(get_db)):
    """KPI values for the dashboard: indicative AQI, water status, active anomalies, active alerts,
    per-rule threshold decisions and the status of each pipeline stage. All values come from stored data."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        return dashboard.summary(db, zone_id, window)
    except Exception as exc:
        raise_http(exc)


@router.get("/zones/{zone_id}/map", response_model=MapResponse, responses=ZONE_ERRORS, summary="Map layers for a zone")
def zone_map(zone_id: str = ZoneId, parameter: ParameterKey = parameter_query(), w: WindowParams = Depends(),
             db: Session = Depends(get_db)):
    """Sensors (latest value, timestamp, quality flag), factories (state, 24 h output trend), events,
    and a sensor-point intensity layer for the selected parameter."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        return dashboard.map_layers(db, zone_id, parameter, window)
    except Exception as exc:
        raise_http(exc)


@router.get("/zones/{zone_id}/trends", response_model=TrendResponse, responses=ZONE_ERRORS,
            summary="Historical trend with factory and event context")
def zone_trends(zone_id: str = ZoneId, parameter: ParameterKey = parameter_query(), w: WindowParams = Depends(),
                db: Session = Depends(get_db)):
    """Zone window means (null where missing — gaps are never interpolated), factory output series and
    event markers aligned to the same windows."""
    try:
        window = dashboard.resolve_window(db, zone_id, w.time_range, w.start, w.end)
        return dashboard.trends(db, zone_id, parameter, window)
    except Exception as exc:
        raise_http(exc)
