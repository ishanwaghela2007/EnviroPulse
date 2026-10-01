"""Demo controls for the SIMULATED DEMO STREAM (disabled when ENABLE_DEMO_CONTROLS=false).
Every action moves real records through the backend pipeline; nothing is animated in the UI."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_demo_controls
from app.models.schemas import OutageRequest
from app.services import demo_stream

router = APIRouter(prefix="/api/v1/demo", tags=["demo (simulated)"], dependencies=[Depends(require_demo_controls)])


@router.get("/status", summary="Demo stream state and golden-scenario step")
def status(db: Session = Depends(get_db)):
    return demo_stream.status(db)


@router.post("/tick", summary="Advance the simulated stream by one window")
def tick(db: Session = Depends(get_db)):
    try:
        return demo_stream.tick(db)
    except demo_stream.DemoError as exc:
        raise HTTPException(409, str(exc))


@router.post("/source-outage", summary="Simulate (or end) an outage of a simulated source")
def outage(body: OutageRequest, db: Session = Depends(get_db)):
    return {"outages": demo_stream.set_outage(db, body.source, body.enabled)}


@router.post("/reset", summary="Truncate, reseed history and rewind the golden scenario (~40 s)")
def reset():
    from app.seed.reset_demo import reset as do_reset
    return {"status": "reset", "seed": do_reset()}
