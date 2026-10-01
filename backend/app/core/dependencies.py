from collections.abc import Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal


def get_db() -> Iterator[Session]:
    """One transaction per request: commit on success, roll back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require_demo_controls() -> None:
    if not get_settings().enable_demo_controls:
        raise HTTPException(status_code=403, detail="Demo controls are disabled (ENABLE_DEMO_CONTROLS=false).")
