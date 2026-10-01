from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import redis as rcache
from app.core.config import get_settings
from app.core.database import check_database
from app.core.dependencies import get_db
from app.core.timeutil import utcnow
from app.models.schemas import HealthResponse
from app.repositories import readings as reading_repo
from app.workers import runner

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="System health")
def health(db: Session = Depends(get_db)):
    """API, database (PostGIS/TimescaleDB versions), Redis and scheduler status, plus the data version
    counter the frontend polls to know when to refresh. Degrades instead of failing when Redis is down."""
    database = check_database()
    red = rcache.check_redis()
    sched = runner.status()
    latest = reading_repo.latest_reading_time(db) if database["status"] == "ok" else None
    ok = database["status"] == "ok" and red["status"] == "ok"
    return {"status": "ok" if ok else "degraded", "server_time": utcnow(),
            "api": {"status": "ok", "detail": {"version": "1.0.0"}},
            "database": {"status": database["status"], "detail": {k: v for k, v in database.items() if k != "status"}},
            "redis": {"status": red["status"], "detail": {k: v for k, v in red.items() if k != "status"}},
            "scheduler": {"status": sched["status"], "detail": sched},
            "data_version": rcache.data_version(), "latest_data_timestamp": latest,
            "demo_controls_enabled": get_settings().enable_demo_controls}
