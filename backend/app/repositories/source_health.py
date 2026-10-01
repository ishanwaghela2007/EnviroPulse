from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_source(db: Session, name: str, label: str, category: str, simulated: bool, status: str,
                  error: str | None = None) -> None:
    db.execute(text("""
        INSERT INTO source_health (source_name, label, category, status, is_simulated, error_message,
                                   consecutive_failures)
        VALUES (:n, :l, :c, :s, :sim, :err, 0) ON CONFLICT (source_name) DO NOTHING"""),
               {"n": name, "l": label, "c": category, "s": status, "sim": simulated, "err": error})


def record_success(db: Session, name: str, now: datetime, latency_ms: float, records: int,
                   latest_data: datetime | None, status: str) -> None:
    db.execute(text("""
        UPDATE source_health SET status=:st, last_successful_fetch=:now, last_attempt=:now, latency=:lat,
               records_last_batch=:n, consecutive_failures=0, error_message=NULL,
               latest_data_timestamp=GREATEST(COALESCE(:ld, latest_data_timestamp), latest_data_timestamp),
               updated_at=now()
        WHERE source_name=:name"""), {"st": status, "now": now, "lat": latency_ms, "n": records, "ld": latest_data,
                                      "name": name})


def record_failure(db: Session, name: str, now: datetime, error: str, offline_after: int = 3) -> str:
    """First failures -> DEGRADED (last-known-good data retained); repeated failures -> OFFLINE."""
    row = db.execute(text("""
        UPDATE source_health SET last_attempt=:now, consecutive_failures=consecutive_failures+1,
               error_message=:err, updated_at=now(),
               status = CASE WHEN last_successful_fetch IS NULL OR consecutive_failures + 1 >= :off
                             THEN 'OFFLINE' ELSE 'DEGRADED' END
        WHERE source_name=:name RETURNING status"""), {"now": now, "err": error[:500], "off": offline_after,
                                                       "name": name}).first()
    return row.status if row else "OFFLINE"


def set_status(db: Session, name: str, status: str, error: str | None) -> None:
    db.execute(text("UPDATE source_health SET status=:s, error_message=:e, last_attempt=now(), updated_at=now() "
                    "WHERE source_name=:n"), {"s": status, "e": error, "n": name})


def list_sources(db: Session) -> list[dict]:
    rows = db.execute(text("SELECT * FROM source_health ORDER BY category, source_name")).all()
    return [r._asdict() for r in rows]
