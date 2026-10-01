from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.parameters import PARAMETERS
from app.models.schemas import AcknowledgeRequest, AlertDetailResponse, AlertItem, AlertsResponse, AlertStatus
from app.repositories import alerts as alert_repo
from app.services import feedback as feedback_service

router = APIRouter(prefix="/api/v1", tags=["alerts"])


def _item(a: dict) -> dict:
    return {**a, "label": PARAMETERS[a["parameter"]].label}


@router.get("/alerts", response_model=AlertsResponse, summary="List alerts (alert log)")
def list_alerts(zone_id: str | None = Query(None, max_length=40), status: AlertStatus | None = Query(None,
                description="active | acknowledged | resolved | dismissed | open (active + acknowledged + dismissed-but-ongoing)"),
                limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    rows = [_item(a) for a in alert_repo.list_alerts(db, zone_id, status, limit)]
    return {"alerts": rows, "count": len(rows)}


@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse, responses={404: {"description": "Not found"}},
            summary="Alert with its full append-only log")
def get_alert(alert_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    a = alert_repo.get_alert(db, alert_id)
    if not a:
        raise HTTPException(404, f"Alert {alert_id} not found.")
    return {**_item(a), "log": alert_repo.alert_events(db, alert_id)}


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertItem,
             responses={404: {"description": "Not found"}, 409: {"description": "Alert is not active"}},
             summary="Acknowledge an active alert")
def acknowledge(body: AcknowledgeRequest, alert_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """Changes status active -> acknowledged and writes the alert log. History is never deleted. The episode
    stays open until values return to normal, so acknowledging does not allow a duplicate alert."""
    try:
        return _item(feedback_service.acknowledge_alert(db, alert_id, body.operator, body.note))
    except feedback_service.FeedbackError as exc:
        raise HTTPException(exc.status_code, str(exc))
