from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_event(db: Session, e: dict) -> bool:
    res = db.execute(text("""
        INSERT INTO events (zone_id, type, start_time, end_time, location, severity, description, source,
                            source_record_id)
        VALUES (:zone_id, :type, :start_time, :end_time, ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326),
                :severity, :description, :source, :source_record_id)
        ON CONFLICT (source_record_id) DO UPDATE SET end_time = EXCLUDED.end_time,
            severity = EXCLUDED.severity, description = EXCLUDED.description
        RETURNING (xmax = 0) AS inserted"""), e).first()
    return bool(res and res.inserted)


def events_overlapping(db: Session, zone_id: str, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(text("""
        SELECT id, type, start_time, end_time, severity, description, source, ST_Y(location) lat, ST_X(location) lon
        FROM events WHERE zone_id = :z AND start_time < :e AND (end_time IS NULL OR end_time > :s)
        ORDER BY start_time"""), {"z": zone_id, "s": start, "e": end}).all()
    return [r._asdict() for r in rows]
