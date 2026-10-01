from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.schemas import SourceHealthResponse
from app.services import dashboard

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/source-health", response_model=SourceHealthResponse, summary="Connector health")
def source_health(db: Session = Depends(get_db)):
    """Per source: HEALTHY | DEGRADED | OFFLINE | SIMULATED, last successful fetch, latency, error and the
    last-known-good batch summary cached in Redis. Simulated sources are always marked SIMULATED."""
    return dashboard.source_health(db)
