import json

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.db_models import Zone


def list_zones(db: Session) -> list[dict]:
    rows = db.execute(select(Zone.id, Zone.name, Zone.description, Zone.status, Zone.boundary_note,
                             func.ST_AsGeoJSON(Zone.geometry).label("geojson"),
                             func.ST_X(func.ST_Centroid(Zone.geometry)).label("lon"),
                             func.ST_Y(func.ST_Centroid(Zone.geometry)).label("lat"))
                      .order_by(Zone.id)).all()
    out = []
    for r in rows:
        d = r._asdict()
        d["geometry"] = json.loads(d.pop("geojson"))
        out.append(d)
    return out


def get_zone(db: Session, zone_id: str) -> dict | None:
    return next((z for z in list_zones(db) if z["id"] == zone_id), None)


def zone_exists(db: Session, zone_id: str) -> bool:
    return db.execute(text("SELECT 1 FROM zones WHERE id=:z"), {"z": zone_id}).first() is not None


def zone_for_point(db: Session, lat: float, lon: float) -> str | None:
    """PostGIS point-in-polygon zone assignment (done at ingestion, never in the frontend)."""
    return db.execute(text("SELECT id FROM zones WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lon,:lat),4326)) "
                           "ORDER BY id LIMIT 1"), {"lat": lat, "lon": lon}).scalar()


def insert_zone(db: Session, z: dict, note: str) -> None:
    wkt = "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in z["polygon"]) + "))"
    db.execute(text("INSERT INTO zones (id, name, description, geometry, status, boundary_note) "
                    "VALUES (:id, :name, :d, ST_GeomFromText(:wkt, 4326), 'active', :note)"),
               {"id": z["id"], "name": z["name"], "d": z["description"], "wkt": wkt, "note": note})
