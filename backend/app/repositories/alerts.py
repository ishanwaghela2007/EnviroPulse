from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def thresholds_for_zone(db: Session, zone_id: str) -> list[dict]:
    """Zone-specific rules override global rules for the same parameter + direction."""
    rows = db.execute(text("""
        SELECT DISTINCT ON (parameter, direction) * FROM thresholds
        WHERE active AND (zone_id = :z OR zone_id IS NULL)
        ORDER BY parameter, direction, zone_id NULLS LAST"""), {"z": zone_id}).all()
    return [r._asdict() for r in rows]


def insert_threshold(db: Session, t: dict) -> None:
    db.execute(text("""INSERT INTO thresholds (zone_id, parameter, threshold_value, direction, persistence_windows,
                       min_confidence, severity, action_text, basis, active)
                       VALUES (:zone_id, :parameter, :threshold_value, :direction, :persistence_windows,
                               :min_confidence, :severity, :action_text, :basis, true)"""), t)


def open_episode(db: Session, zone_id: str, parameter: str, threshold_id: int) -> dict | None:
    row = db.execute(text("SELECT * FROM alerts WHERE zone_id=:z AND parameter=:p AND threshold_id=:t "
                          "AND episode_open FOR UPDATE"), {"z": zone_id, "p": parameter, "t": threshold_id}).first()
    return row._asdict() if row else None


def create_alert(db: Session, a: dict) -> int:
    return db.execute(text("""
        INSERT INTO alerts (zone_id, parameter, threshold_id, value, peak_value, threshold, unit, direction, reason,
                            source_context, severity, action_text, status, episode_open, breach_windows,
                            first_breach_at, last_breach_at)
        VALUES (:zone_id, :parameter, :threshold_id, :value, :value, :threshold, :unit, :direction, :reason,
                :source_context, :severity, :action_text, 'active', true, :breach_windows, :first_breach_at,
                :last_breach_at)
        RETURNING id"""), a).scalar_one()


def update_alert(db: Session, alert_id: int, value: float, reason: str, context: str, breach_windows: int,
                 last_breach_at: datetime, direction: str) -> None:
    peak = "GREATEST(peak_value, :v)" if direction == "above" else "LEAST(peak_value, :v)"
    db.execute(text(f"""UPDATE alerts SET value=:v, peak_value={peak}, reason=:r, source_context=:c,
                        breach_windows=:b, last_breach_at=:t, updated_at=now() WHERE id=:id"""),
               {"v": value, "r": reason, "c": context, "b": breach_windows, "t": last_breach_at, "id": alert_id})


def close_episode(db: Session, alert_id: int, at: datetime) -> str:
    return db.execute(text("""
        UPDATE alerts SET episode_open=false, resolved_at=:t, updated_at=now(),
               status = CASE WHEN status IN ('active','acknowledged') THEN 'resolved' ELSE status END
        WHERE id=:id RETURNING status"""), {"t": at, "id": alert_id}).scalar_one()


def log_event(db: Session, alert_id: int, event_type: str, message: str, value: float | None = None,
              data_ts: datetime | None = None) -> None:
    db.execute(text("INSERT INTO alert_events (alert_id, event_type, message, value, data_timestamp) "
                    "VALUES (:a, :t, :m, :v, :d)"), {"a": alert_id, "t": event_type, "m": message, "v": value,
                                                     "d": data_ts})


def get_alert(db: Session, alert_id: int) -> dict | None:
    row = db.execute(text("SELECT a.*, z.name AS zone_name FROM alerts a JOIN zones z ON z.id=a.zone_id "
                          "WHERE a.id=:id"), {"id": alert_id}).first()
    return row._asdict() if row else None


def list_alerts(db: Session, zone_id: str | None, status: str | None, limit: int) -> list[dict]:
    q = "SELECT a.*, z.name AS zone_name FROM alerts a JOIN zones z ON z.id=a.zone_id WHERE true"
    p: dict = {"lim": limit}
    if zone_id:
        q += " AND a.zone_id=:z"
        p["z"] = zone_id
    if status == "open":
        q += " AND a.episode_open"
    elif status:
        q += " AND a.status=:s"
        p["s"] = status
    q += " ORDER BY a.episode_open DESC, a.last_breach_at DESC, a.id DESC LIMIT :lim"
    return [r._asdict() for r in db.execute(text(q), p).all()]


def alert_events(db: Session, alert_id: int) -> list[dict]:
    rows = db.execute(text("SELECT * FROM alert_events WHERE alert_id=:a ORDER BY id"), {"a": alert_id}).all()
    return [r._asdict() for r in rows]


def acknowledge(db: Session, alert_id: int, operator: str, at: datetime) -> bool:
    res = db.execute(text("""UPDATE alerts SET status='acknowledged', acknowledged_at=:t, acknowledged_by=:o,
                             updated_at=now() WHERE id=:id AND status='active' RETURNING id"""),
                     {"t": at, "o": operator, "id": alert_id}).first()
    return res is not None


def dismiss(db: Session, alert_id: int) -> bool:
    res = db.execute(text("""UPDATE alerts SET status='dismissed', updated_at=now()
                             WHERE id=:id AND status IN ('active','acknowledged') RETURNING id"""),
                     {"id": alert_id}).first()
    return res is not None


def count_open(db: Session, zone_id: str) -> dict:
    row = db.execute(text("""SELECT count(*) FILTER (WHERE status='active') active,
                                    count(*) FILTER (WHERE status='acknowledged') acknowledged,
                                    count(*) FILTER (WHERE status='dismissed') dismissed
                             FROM alerts WHERE zone_id=:z AND episode_open"""), {"z": zone_id}).first()
    return row._asdict()
