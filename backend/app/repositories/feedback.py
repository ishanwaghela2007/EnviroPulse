from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_feedback(db: Session, f: dict) -> dict:
    row = db.execute(text("""
        INSERT INTO feedback (zone_id, alert_id, anomaly_id, feedback_type, feedback_text, contributor_type,
                              contributor_id, operator)
        VALUES (:zone_id, :alert_id, :anomaly_id, :feedback_type, :feedback_text, :contributor_type,
                :contributor_id, :operator) RETURNING *"""), f).first()
    return row._asdict()


def list_feedback(db: Session, zone_id: str | None, alert_id: int | None, limit: int) -> list[dict]:
    q = "SELECT * FROM feedback WHERE true"
    p: dict = {"lim": limit}
    if zone_id:
        q += " AND zone_id=:z"
        p["z"] = zone_id
    if alert_id:
        q += " AND alert_id=:a"
        p["a"] = alert_id
    q += " ORDER BY created_at DESC, id DESC LIMIT :lim"
    return [r._asdict() for r in db.execute(text(q), p).all()]
