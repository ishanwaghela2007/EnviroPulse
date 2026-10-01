import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

INSERT_READINGS = text("""
    INSERT INTO readings (timestamp, sensor_id, zone_id, original_timestamp, parameter, value, unit,
                          quality_flag, quality_reason, source, source_record_id)
    SELECT * FROM unnest(CAST(:timestamp AS timestamptz[]), CAST(:sensor_id AS text[]), CAST(:zone_id AS text[]),
                         CAST(:original_timestamp AS text[]), CAST(:parameter AS text[]),
                         CAST(:value AS double precision[]), CAST(:unit AS text[]), CAST(:quality_flag AS text[]),
                         CAST(:quality_reason AS text[]), CAST(:source AS text[]), CAST(:source_record_id AS text[]))
    ON CONFLICT ON CONSTRAINT uq_readings_source_record DO NOTHING
    RETURNING id
""")
_COLS = ["timestamp", "sensor_id", "zone_id", "original_timestamp", "parameter", "value", "unit",
         "quality_flag", "quality_reason", "source", "source_record_id"]


def insert_readings(db: Session, rows: list[dict], chunk: int = 5000) -> int:
    """Bulk insert; duplicates are skipped by the DB unique constraint. Returns rows actually inserted."""
    inserted = 0
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        inserted += len(db.execute(INSERT_READINGS, {c: [r[c] for r in part] for c in _COLS}).all())
    return inserted


def insert_water_observations(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    cols = ["sensor_id", "zone_id", "timestamp", "parameter", "value", "unit", "status", "source"]
    db.execute(text("""
        INSERT INTO water_observations (sensor_id, zone_id, timestamp, parameter, value, unit, status, source)
        SELECT * FROM unnest(CAST(:sensor_id AS text[]), CAST(:zone_id AS text[]), CAST(:timestamp AS timestamptz[]),
                             CAST(:parameter AS text[]), CAST(:value AS double precision[]), CAST(:unit AS text[]),
                             CAST(:status AS text[]), CAST(:source AS text[]))
        ON CONFLICT ON CONSTRAINT uq_water_obs DO NOTHING"""), {c: [r[c] for r in rows] for c in cols})


def quarantine(db: Session, source: str, record_id: str | None, payload: dict, reason: str) -> None:
    db.execute(text("INSERT INTO quarantined_records (source, source_record_id, payload, reason) "
                    "VALUES (:s, :r, CAST(:p AS JSONB), :reason)"),
               {"s": source, "r": record_id, "p": json.dumps(payload, default=str), "reason": reason[:300]})


def zone_bucket_aggregates(db: Session, zone_id: str, start: datetime, end: datetime, minutes: int) -> list[dict]:
    """Aggregate VALID readings per zone/parameter/window. Non-VALID readings are counted but excluded
    from the mean, so a MISSING/SUSPICIOUS/STALE value can never distort the zone value."""
    rows = db.execute(text("""
        SELECT date_bin(make_interval(mins => :m), timestamp, TIMESTAMPTZ '2000-01-01') AS bucket, parameter,
               avg(value) FILTER (WHERE quality_flag = 'VALID') AS mean,
               count(DISTINCT sensor_id) FILTER (WHERE quality_flag = 'VALID') AS valid_sensors,
               count(*) AS total
        FROM readings WHERE zone_id = :z AND timestamp >= :s AND timestamp < :e
        GROUP BY 1, 2 ORDER BY 1"""), {"z": zone_id, "s": start, "e": end, "m": minutes}).all()
    return [r._asdict() for r in rows]


def latest_sensor_readings(db: Session, zone_id: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT DISTINCT ON (sensor_id, parameter) sensor_id, parameter, value, unit, timestamp, quality_flag,
               quality_reason, source
        FROM readings WHERE zone_id = :z
          AND timestamp > (SELECT max(timestamp) FROM readings WHERE zone_id = :z) - interval '1 day'
        ORDER BY sensor_id, parameter, timestamp DESC"""), {"z": zone_id}).all()
    return [r._asdict() for r in rows]


def sensor_series(db: Session, sensor_id: str, parameter: str, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(text("""SELECT timestamp, value, quality_flag FROM readings WHERE sensor_id=:s AND parameter=:p
                              AND timestamp>=:a AND timestamp<=:b ORDER BY timestamp"""),
                      {"s": sensor_id, "p": parameter, "a": start, "b": end}).all()
    return [r._asdict() for r in rows]


def latest_reading_time(db: Session, zone_id: str | None = None) -> datetime | None:
    if zone_id:
        return db.execute(text("SELECT max(timestamp) FROM readings WHERE zone_id=:z"), {"z": zone_id}).scalar()
    return db.execute(text("SELECT max(timestamp) FROM readings")).scalar()


def quality_summary(db: Session, zone_id: str, start: datetime, end: datetime) -> dict:
    rows = db.execute(text("SELECT quality_flag, count(*) n FROM readings WHERE zone_id=:z AND timestamp>=:s "
                           "AND timestamp<=:e GROUP BY 1"), {"z": zone_id, "s": start, "e": end}).all()
    return {r.quality_flag: r.n for r in rows}


def quarantine_count(db: Session) -> int:
    return db.execute(text("SELECT count(*) FROM quarantined_records")).scalar()
