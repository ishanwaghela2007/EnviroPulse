"""Feature / anomaly / attribution / forecast / AQI / pipeline-state persistence."""
import json
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_features(db: Session, rows: list[dict], chunk: int = 5000) -> None:
    cols = ["zone_id", "timestamp", "feature_name", "value", "unit", "source_window"]
    # de-duplicate within the batch (ON CONFLICT DO UPDATE cannot touch the same row twice)
    dedup = {(r["zone_id"], r["timestamp"], r["feature_name"]): r for r in rows}
    rows = list(dedup.values())
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        db.execute(text("""
            INSERT INTO features (zone_id, timestamp, feature_name, value, unit, source_window)
            SELECT * FROM unnest(CAST(:zone_id AS text[]), CAST(:timestamp AS timestamptz[]),
                                 CAST(:feature_name AS text[]), CAST(:value AS double precision[]),
                                 CAST(:unit AS text[]), CAST(:source_window AS text[]))
            ON CONFLICT ON CONSTRAINT uq_feature DO UPDATE SET value=EXCLUDED.value, unit=EXCLUDED.unit,
                source_window=EXCLUDED.source_window"""), {c: [r[c] for r in part] for c in cols})


def feature_frame(db: Session, zone_id: str, names: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    """Wide frame indexed by window timestamp (inclusive start and end)."""
    rows = db.execute(text("""SELECT timestamp, feature_name, value FROM features
                              WHERE zone_id=:z AND feature_name = ANY(:n) AND timestamp>=:s AND timestamp<=:e"""),
                      {"z": zone_id, "n": names, "s": start, "e": end}).all()
    if not rows:
        return pd.DataFrame(columns=names, dtype=float)
    df = pd.DataFrame(rows, columns=["timestamp", "feature_name", "value"])
    df["value"] = df["value"].astype(float)
    wide = df.pivot_table(index="timestamp", columns="feature_name", values="value", aggfunc="first", dropna=False)
    for n in names:
        if n not in wide.columns:
            wide[n] = float("nan")
    return wide[names].sort_index()


def latest_feature_time(db: Session, zone_id: str, name: str) -> datetime | None:
    return db.execute(text("SELECT max(timestamp) FROM features WHERE zone_id=:z AND feature_name=:n "
                           "AND value IS NOT NULL"), {"z": zone_id, "n": name}).scalar()


def latest_features(db: Session, zone_id: str, names: list[str], at: datetime) -> dict:
    rows = db.execute(text("SELECT feature_name, value, unit FROM features WHERE zone_id=:z AND timestamp=:t "
                           "AND feature_name = ANY(:n)"), {"z": zone_id, "t": at, "n": names}).all()
    return {r.feature_name: r._asdict() for r in rows}


def anomaly_timestamps(db: Session, zone_id: str, parameter: str, start: datetime, end: datetime,
                       version: str) -> set:
    return set(db.execute(text("""SELECT timestamp FROM anomalies WHERE zone_id=:z AND parameter=:p AND timestamp>=:s
                                  AND timestamp<:e AND detector_version=:v"""),
                          {"z": zone_id, "p": parameter, "s": start, "e": end, "v": version}).scalars())


def upsert_anomaly(db: Session, a: dict) -> tuple[int, bool]:
    row = db.execute(text("""
        INSERT INTO anomalies (zone_id, timestamp, parameter, value, score, direction, baseline_mean, baseline_low,
                               baseline_high, reason, detector_version)
        VALUES (:zone_id, :timestamp, :parameter, :value, :score, :direction, :baseline_mean, :baseline_low,
                :baseline_high, :reason, :detector_version)
        ON CONFLICT ON CONSTRAINT uq_anomaly DO UPDATE SET value=EXCLUDED.value, score=EXCLUDED.score,
            direction=EXCLUDED.direction, baseline_mean=EXCLUDED.baseline_mean, baseline_low=EXCLUDED.baseline_low,
            baseline_high=EXCLUDED.baseline_high, reason=EXCLUDED.reason
        RETURNING id, (xmax = 0) AS inserted"""), a).first()
    return row.id, bool(row.inserted)


def delete_anomalies_not_in(db: Session, zone_id: str, parameter: str, start: datetime, end: datetime,
                            keep: list[datetime], version: str) -> None:
    db.execute(text("""DELETE FROM anomalies WHERE zone_id=:z AND parameter=:p AND timestamp>=:s AND timestamp<=:e
                       AND detector_version=:v AND NOT (timestamp = ANY(:k))"""),
               {"z": zone_id, "p": parameter, "s": start, "e": end, "v": version, "k": keep})


def list_anomalies(db: Session, zone_id: str, parameter: str | None, start: datetime, end: datetime,
                   limit: int = 500) -> list[dict]:
    q = """SELECT a.*, (SELECT count(*) FROM attributions t WHERE t.anomaly_id=a.id) AS attribution_count
           FROM anomalies a WHERE zone_id=:z AND timestamp>=:s AND timestamp<=:e"""
    p = {"z": zone_id, "s": start, "e": end, "lim": limit}
    if parameter:
        q += " AND parameter=:p"
        p["p"] = parameter
    q += " ORDER BY timestamp DESC LIMIT :lim"
    return [r._asdict() for r in db.execute(text(q), p).all()]


def count_anomalies(db: Session, zone_id: str, start: datetime, end: datetime) -> int:
    return db.execute(text("SELECT count(*) FROM anomalies WHERE zone_id=:z AND timestamp>=:s AND timestamp<=:e"),
                      {"z": zone_id, "s": start, "e": end}).scalar()


def get_anomaly(db: Session, anomaly_id: int) -> dict | None:
    r = db.execute(text("SELECT * FROM anomalies WHERE id=:id"), {"id": anomaly_id}).first()
    return r._asdict() if r else None


def anomalies_without_attribution(db: Session, zone_id: str, start: datetime, end: datetime) -> list[dict]:
    rows = db.execute(text("""SELECT a.* FROM anomalies a WHERE a.zone_id=:z AND a.timestamp>=:s AND a.timestamp<=:e
                              AND NOT EXISTS (SELECT 1 FROM attributions t WHERE t.anomaly_id=a.id)
                              ORDER BY a.timestamp"""), {"z": zone_id, "s": start, "e": end}).all()
    return [r._asdict() for r in rows]


def insert_attributions(db: Session, rows: list[dict]) -> None:
    for r in rows:
        db.execute(text("""
            INSERT INTO attributions (anomaly_id, contributor_type, contributor_id, contributor_name, rank, score,
                                      correlation, best_lag_windows, deviation, evidence, time_window_start,
                                      time_window_end, data_quality, method_version)
            VALUES (:anomaly_id, :contributor_type, :contributor_id, :contributor_name, :rank, :score, :correlation,
                    :best_lag_windows, :deviation, :evidence, :time_window_start, :time_window_end,
                    CAST(:data_quality AS JSONB), :method_version)"""),
                   {**r, "data_quality": json.dumps(r["data_quality"])})


def attributions_for(db: Session, anomaly_id: int) -> list[dict]:
    rows = db.execute(text("SELECT * FROM attributions WHERE anomaly_id=:a ORDER BY rank"), {"a": anomaly_id}).all()
    return [r._asdict() for r in rows]


def upsert_aqi(db: Session, rows: list[dict]) -> None:
    for r in rows:
        db.execute(text("""
            INSERT INTO aqi_snapshots (zone_id, timestamp, aqi, category, dominant_parameter, source, method)
            VALUES (:zone_id, :timestamp, :aqi, :category, :dominant_parameter, :source, :method)
            ON CONFLICT ON CONSTRAINT uq_aqi_zone_ts_source DO UPDATE SET aqi=EXCLUDED.aqi,
                category=EXCLUDED.category, dominant_parameter=EXCLUDED.dominant_parameter"""), r)


def latest_aqi(db: Session, zone_id: str) -> dict | None:
    r = db.execute(text("SELECT * FROM aqi_snapshots WHERE zone_id=:z ORDER BY timestamp DESC LIMIT 1"),
                   {"z": zone_id}).first()
    return r._asdict() if r else None


def latest_forecast_run(db: Session, zone_id: str, parameter: str) -> list[dict]:
    run = db.execute(text("""SELECT run_id FROM forecasts WHERE zone_id=:z AND parameter=:p
                             ORDER BY generated_at DESC, id DESC LIMIT 1"""), {"z": zone_id, "p": parameter}).scalar()
    if not run:
        return []
    rows = db.execute(text("SELECT * FROM forecasts WHERE run_id=:r ORDER BY target_time"), {"r": run}).all()
    return [r._asdict() for r in rows]


def insert_forecast_rows(db: Session, rows: list[dict]) -> None:
    for r in rows:
        db.execute(text("""
            INSERT INTO forecasts (run_id, zone_id, parameter, generated_at, based_on_until, target_time, prediction,
                                   lower_bound, upper_bound, model, model_version, validation_metadata)
            VALUES (:run_id, :zone_id, :parameter, :generated_at, :based_on_until, :target_time, :prediction,
                    :lower_bound, :upper_bound, :model, :model_version, CAST(:validation_metadata AS JSONB))"""),
                   {**r, "validation_metadata": json.dumps(r["validation_metadata"], default=str)})


def get_state(db: Session, key: str) -> dict | None:
    return db.execute(text("SELECT value FROM pipeline_state WHERE key=:k"), {"k": key}).scalar()


def set_state(db: Session, key: str, value: dict) -> None:
    db.execute(text("""INSERT INTO pipeline_state (key, value) VALUES (:k, CAST(:v AS JSONB))
                       ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()"""),
               {"k": key, "v": json.dumps(value, default=str)})
