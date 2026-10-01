from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_factory(db: Session, f: dict, zone_id: str | None) -> None:
    db.execute(text("""INSERT INTO factories (id, zone_id, name, sector, geometry, status)
                       VALUES (:id, :zone, :name, :sector, ST_SetSRID(ST_MakePoint(:lon,:lat),4326), 'operating')
                       ON CONFLICT (id) DO NOTHING"""),
               {"id": f["id"], "zone": zone_id, "name": f["name"], "sector": f["sector"], "lat": f["lat"],
                "lon": f["lon"]})


def factory_ids(db: Session) -> set[str]:
    return set(db.execute(text("SELECT id FROM factories")).scalars())


def zone_factories(db: Session, zone_id: str) -> list[dict]:
    rows = db.execute(text("""SELECT id, name, sector, status, ST_Y(geometry) lat, ST_X(geometry) lon
                              FROM factories WHERE zone_id=:z ORDER BY id"""), {"z": zone_id}).all()
    return [r._asdict() for r in rows]


def insert_outputs(db: Session, rows: list[dict], chunk: int = 5000) -> int:
    cols = ["factory_id", "timestamp", "metric", "value", "unit", "operating_state", "source"]
    n = 0
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        n += len(db.execute(text("""
            INSERT INTO factory_outputs (factory_id, timestamp, metric, value, unit, operating_state, source)
            SELECT * FROM unnest(CAST(:factory_id AS text[]), CAST(:timestamp AS timestamptz[]),
                                 CAST(:metric AS text[]), CAST(:value AS double precision[]), CAST(:unit AS text[]),
                                 CAST(:operating_state AS text[]), CAST(:source AS text[]))
            ON CONFLICT ON CONSTRAINT uq_factory_output DO NOTHING RETURNING id"""),
            {c: [r[c] for r in part] for c in cols}).all())
    return n


def update_status(db: Session, factory_id: str, state: str | None) -> None:
    if state:
        db.execute(text("UPDATE factories SET status=:s WHERE id=:id"), {"s": state, "id": factory_id})


def bucket_outputs(db: Session, zone_id: str, start: datetime, end: datetime, minutes: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT date_bin(make_interval(mins => :m), o.timestamp, TIMESTAMPTZ '2000-01-01') AS bucket,
               o.factory_id, avg(o.value) AS value
        FROM factory_outputs o JOIN factories f ON f.id = o.factory_id
        WHERE f.zone_id = :z AND o.metric = 'production_level' AND o.timestamp >= :s AND o.timestamp < :e
        GROUP BY 1, 2 ORDER BY 1"""), {"z": zone_id, "s": start, "e": end, "m": minutes}).all()
    return [r._asdict() for r in rows]


def latest_outputs(db: Session, zone_id: str) -> dict[str, dict]:
    rows = db.execute(text("""
        SELECT DISTINCT ON (o.factory_id) o.factory_id, o.timestamp, o.value, o.unit, o.operating_state
        FROM factory_outputs o JOIN factories f ON f.id=o.factory_id WHERE f.zone_id=:z
        ORDER BY o.factory_id, o.timestamp DESC"""), {"z": zone_id}).all()
    return {r.factory_id: r._asdict() for r in rows}


def output_series(db: Session, factory_id: str, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(text("""SELECT timestamp, value, unit, operating_state FROM factory_outputs
                              WHERE factory_id=:f AND timestamp>=:s AND timestamp<=:e ORDER BY timestamp"""),
                      {"f": factory_id, "s": start, "e": end}).all()
    return [r._asdict() for r in rows]
