from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.db_models import Sensor


def get_sensor_map(db: Session) -> dict[str, dict]:
    rows = db.execute(select(Sensor.id, Sensor.zone_id, Sensor.type, Sensor.source, Sensor.active,
                             Sensor.parameters)).all()
    return {r.id: r._asdict() for r in rows}


def upsert_sensor(db: Session, sid: str, zone_id: str | None, stype: str, name: str, lat: float, lon: float,
                  source: str, parameters: list[str]) -> None:
    db.execute(text("""
        INSERT INTO sensors (id, zone_id, type, name, latitude, longitude, geometry, source, parameters, active)
        VALUES (:id, :zone, :type, :name, :lat, :lon, ST_SetSRID(ST_MakePoint(:lon,:lat),4326), :source, :params, true)
        ON CONFLICT (id) DO UPDATE SET parameters = (
            SELECT ARRAY(SELECT DISTINCT unnest(sensors.parameters || EXCLUDED.parameters)))
    """), {"id": sid, "zone": zone_id, "type": stype, "name": name, "lat": lat, "lon": lon, "source": source,
           "params": parameters})


def zone_sensors(db: Session, zone_id: str) -> list[dict]:
    rows = db.execute(text("""SELECT id, type, name, latitude, longitude, source, parameters, active
                              FROM sensors WHERE zone_id = :z ORDER BY type, id"""), {"z": zone_id}).all()
    return [r._asdict() for r in rows]


def expected_sensor_counts(db: Session, zone_id: str) -> dict[str, int]:
    rows = db.execute(text("SELECT unnest(parameters) p, count(*) n FROM sensors WHERE zone_id=:z AND active "
                           "GROUP BY 1"), {"z": zone_id}).all()
    return {r.p: r.n for r in rows}
