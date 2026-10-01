"""Analytics worker: alignment -> anomaly -> attribution -> alerts -> forecast for new data."""
from app.core.database import session_scope
from app.services import pipeline


def run_pending() -> int:
    with session_scope() as db:
        return len(pipeline.process_pending(db))
