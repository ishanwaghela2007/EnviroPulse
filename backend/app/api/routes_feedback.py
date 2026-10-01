from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.schemas import FeedbackItem, FeedbackListResponse, FeedbackRequest
from app.repositories import feedback as feedback_repo
from app.services import feedback as feedback_service

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackItem, status_code=201,
             responses={404: {"description": "Zone/alert/anomaly not found"}, 422: {"description": "Invalid feedback"}},
             summary="Record operator feedback")
def create_feedback(body: FeedbackRequest, db: Session = Depends(get_db)):
    """Types: confirm, dismiss, false_positive, tag_factory, tag_event, sensor_issue, note. Persisted for
    future threshold/model recalibration. 'dismiss'/'false_positive' on an alert set it to dismissed."""
    try:
        return feedback_service.submit_feedback(db, body.model_dump())
    except feedback_service.FeedbackError as exc:
        raise HTTPException(exc.status_code, str(exc))


@router.get("/feedback", response_model=FeedbackListResponse, summary="List operator feedback")
def list_feedback(zone_id: str | None = Query(None, max_length=40), alert_id: int | None = Query(None, ge=1),
                  limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return {"feedback": feedback_repo.list_feedback(db, zone_id, alert_id, limit)}
