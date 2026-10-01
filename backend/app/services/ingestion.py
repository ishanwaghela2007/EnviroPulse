"""Ingestion: normalize -> validate -> resolve zone (PostGIS) -> dedupe -> store.
Invalid records are quarantined with a reason code; missing values are stored as NULL / MISSING."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import log
from app.core.parameters import PARAMETERS
from app.repositories import alerts as alert_repo
from app.repositories import events as event_repo
from app.repositories import factories as factory_repo
from app.repositories import readings as reading_repo
from app.repositories import sensors as sensor_repo
from app.repositories import zones as zone_repo
from app.services import validation

logger = logging.getLogger("enviropulse.ingestion")


@dataclass
class IngestResult:
    received: int = 0
    accepted: int = 0
    inserted: int = 0
    duplicates: int = 0
    quarantined: int = 0
    by_flag: dict = field(default_factory=dict)
    quarantine_reasons: dict = field(default_factory=dict)
    min_ts: datetime | None = None
    max_ts: datetime | None = None
    zones: set = field(default_factory=set)

    def span(self, ts: datetime, zone: str | None) -> None:
        self.min_ts = ts if self.min_ts is None or ts < self.min_ts else self.min_ts
        self.max_ts = ts if self.max_ts is None or ts > self.max_ts else self.max_ts
        if zone:
            self.zones.add(zone)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["zones"] = sorted(self.zones)
        return d


def _quarantine(db: Session, res: IngestResult, raw, reason: str) -> None:
    source = str(raw.get("source") or "unknown") if isinstance(raw, dict) else "unknown"
    rid = raw.get("source_record_id") if isinstance(raw, dict) else None
    reading_repo.quarantine(db, source, rid, raw if isinstance(raw, dict) else {"raw": str(raw)}, reason)
    res.quarantined += 1
    code = ":".join(reason.split(":")[:2])
    res.quarantine_reasons[code] = res.quarantine_reasons.get(code, 0) + 1


def water_status(value: float | None, rules: list[dict]) -> str:
    if value is None:
        return "no_data"
    for t in rules:
        if (t["direction"] == "above" and value > t["threshold_value"]) or \
           (t["direction"] == "below" and value < t["threshold_value"]):
            return "outside_limits"
    return "within_limits"


def ingest_observations(db: Session, raws: list[dict], now: datetime) -> IngestResult:
    stale_after = timedelta(minutes=get_settings().stale_after_minutes)
    sensors = sensor_repo.get_sensor_map(db)
    res = IngestResult(received=len(raws))
    rows: list[dict] = []
    seen: set = set()
    for raw in raws:
        vr = validation.validate_observation(raw, now, stale_after)
        if not vr.accepted:
            _quarantine(db, res, raw, vr.reason or "invalid")
            continue
        rec = vr.record
        sid = rec["sensor_id"]
        if sid and sid in sensors:
            zone_id = sensors[sid]["zone_id"]
        elif rec["latitude"] is not None:
            # Unknown sensor with coordinates (e.g. a public station): assign zone with PostGIS
            zone_id = zone_repo.zone_for_point(db, rec["latitude"], rec["longitude"])
            if zone_id is None:
                _quarantine(db, res, raw, "geo:outside_configured_zones")
                continue
            sid = sid or f"{rec['source']}:{rec['latitude']:.4f},{rec['longitude']:.4f}"
            stype = PARAMETERS[rec["parameter"]].domain
            sensor_repo.upsert_sensor(db, sid, zone_id, stype, rec.get("sensor_name") or sid, rec["latitude"],
                                      rec["longitude"], rec["source"], [rec["parameter"]])
            sensors[sid] = {"zone_id": zone_id, "type": stype}
        else:
            _quarantine(db, res, raw, "schema:unknown_sensor")
            continue
        if zone_id is None:
            _quarantine(db, res, raw, "geo:sensor_not_assigned_to_zone")
            continue
        key = (rec["source"], rec["source_record_id"], rec["timestamp"])
        if key in seen:
            res.duplicates += 1
            continue
        seen.add(key)
        rec.update(sensor_id=sid, zone_id=zone_id)
        rows.append(rec)
        res.accepted += 1
        res.by_flag[rec["quality_flag"]] = res.by_flag.get(rec["quality_flag"], 0) + 1
        res.span(rec["timestamp"], zone_id)

    res.inserted = reading_repo.insert_readings(db, rows)
    res.duplicates += len(rows) - res.inserted

    rules_cache: dict[str, list[dict]] = {}
    water_rows = []
    for r in rows:
        if PARAMETERS[r["parameter"]].domain != "water":
            continue
        rules = rules_cache.setdefault(r["zone_id"], alert_repo.thresholds_for_zone(db, r["zone_id"]))
        value = r["value"] if r["quality_flag"] == "VALID" else None
        water_rows.append({"sensor_id": r["sensor_id"], "zone_id": r["zone_id"], "timestamp": r["timestamp"],
                           "parameter": r["parameter"], "value": r["value"], "unit": r["unit"],
                           "status": water_status(value, [t for t in rules if t["parameter"] == r["parameter"]]),
                           "source": r["source"]})
    reading_repo.insert_water_observations(db, water_rows)
    log(logger, logging.INFO, "observations ingested", received=res.received, inserted=res.inserted,
        duplicates=res.duplicates, quarantined=res.quarantined, flags=res.by_flag)
    if res.quarantined:
        log(logger, logging.WARNING, "validation failures quarantined", reasons=res.quarantine_reasons)
    return res


def ingest_factory_outputs(db: Session, raws: list[dict], now: datetime) -> IngestResult:
    known = factory_repo.factory_ids(db)
    res = IngestResult(received=len(raws))
    rows = []
    for raw in raws:
        vr = validation.validate_factory_output(raw, now)
        if not vr.accepted:
            _quarantine(db, res, raw, vr.reason or "invalid")
            continue
        if vr.record["factory_id"] not in known:
            _quarantine(db, res, raw, "schema:unknown_factory")
            continue
        rows.append(vr.record)
        res.accepted += 1
        res.span(vr.record["timestamp"], None)
    res.inserted = factory_repo.insert_outputs(db, rows)
    res.duplicates = len(rows) - res.inserted
    latest: dict[str, dict] = {}
    for r in rows:
        if r["factory_id"] not in latest or r["timestamp"] > latest[r["factory_id"]]["timestamp"]:
            latest[r["factory_id"]] = r
    for fid, r in latest.items():
        factory_repo.update_status(db, fid, r.get("operating_state"))
    log(logger, logging.INFO, "factory outputs ingested", inserted=res.inserted, quarantined=res.quarantined)
    return res


def ingest_events(db: Session, raws: list[dict]) -> IngestResult:
    res = IngestResult(received=len(raws))
    for raw in raws:
        vr = validation.validate_event(raw)
        if not vr.accepted:
            _quarantine(db, res, raw, vr.reason or "invalid")
            continue
        e = vr.record
        e["zone_id"] = zone_repo.zone_for_point(db, e["latitude"], e["longitude"])  # PostGIS geo assignment
        if e["zone_id"] is None:
            _quarantine(db, res, raw, "geo:outside_configured_zones")
            continue
        res.accepted += 1
        res.inserted += event_repo.upsert_event(db, e)
        res.span(e["start_time"], e["zone_id"])
    if raws:
        log(logger, logging.INFO, "events ingested", accepted=res.accepted, quarantined=res.quarantined)
    return res
