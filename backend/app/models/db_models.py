"""ORM models. Schema is created ONLY through Alembic migrations (migrations/versions)."""
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (BigInteger, Boolean, DateTime, Float, ForeignKey, Identity, Index, Integer, String, Text,
                        UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TZ = DateTime(timezone=True)


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    geometry = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    boundary_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now(), onupdate=func.now())


class Sensor(Base):
    __tablename__ = "sensors"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), index=True)
    type: Mapped[str] = mapped_column(String(10))  # air | water
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geometry = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    source: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class Reading(Base):
    """Normalized environmental observation. Composite PK (id, timestamp) keeps the
    table compatible with a TimescaleDB hypertable partitioned on timestamp."""
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(TZ, primary_key=True)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id"))
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    original_timestamp: Mapped[str] = mapped_column(String(64))
    parameter: Mapped[str] = mapped_column(String(30))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # NULL preserves missingness
    unit: Mapped[str] = mapped_column(String(16))
    quality_flag: Mapped[str] = mapped_column(String(12))  # VALID | MISSING | SUSPICIOUS | STALE
    quality_reason: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(40))
    source_record_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("source", "source_record_id", "timestamp", name="uq_readings_source_record"),
        Index("ix_readings_ts_zone_param", "timestamp", "zone_id", "parameter"),
        Index("ix_readings_created_at", "created_at"),
    )


class QuarantinedRecord(Base):
    __tablename__ = "quarantined_records"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(300))
    received_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now(), index=True)


class AqiSnapshot(Base):
    __tablename__ = "aqi_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    timestamp: Mapped[datetime] = mapped_column(TZ)
    aqi: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(20))
    dominant_parameter: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("zone_id", "timestamp", "source", name="uq_aqi_zone_ts_source"),)


class WaterObservation(Base):
    __tablename__ = "water_observations"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id"))
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    timestamp: Mapped[datetime] = mapped_column(TZ)
    parameter: Mapped[str] = mapped_column(String(30))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20))  # within_limits | outside_limits | no_data
    source: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("sensor_id", "timestamp", "parameter", name="uq_water_obs"),
                      Index("ix_water_obs_zone_ts", "zone_id", "timestamp"))


class Factory(Base):
    __tablename__ = "factories"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sector: Mapped[str] = mapped_column(String(80))
    geometry = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="operating")


class FactoryOutput(Base):
    __tablename__ = "factory_outputs"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.id"))
    timestamp: Mapped[datetime] = mapped_column(TZ)
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    operating_state: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    __table_args__ = (UniqueConstraint("factory_id", "timestamp", "metric", name="uq_factory_output"),
                      Index("ix_factory_outputs_ts_factory", "timestamp", "factory_id"))


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"))
    type: Mapped[str] = mapped_column(String(40))
    start_time: Mapped[datetime] = mapped_column(TZ)
    end_time: Mapped[datetime | None] = mapped_column(TZ)
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(12))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40))
    source_record_id: Mapped[str] = mapped_column(String(160), unique=True)
    __table_args__ = (Index("ix_events_time_zone", "start_time", "end_time", "zone_id"),)


class Feature(Base):
    __tablename__ = "features"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    timestamp: Mapped[datetime] = mapped_column(TZ)
    feature_name: Mapped[str] = mapped_column(String(80))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    source_window: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("zone_id", "timestamp", "feature_name", name="uq_feature"),
                      Index("ix_features_zone_name_ts", "zone_id", "feature_name", "timestamp"))


class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    timestamp: Mapped[datetime] = mapped_column(TZ)
    parameter: Mapped[str] = mapped_column(String(30))
    value: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(8))
    baseline_mean: Mapped[float] = mapped_column(Float)
    baseline_low: Mapped[float] = mapped_column(Float)
    baseline_high: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    detector_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    __table_args__ = (UniqueConstraint("zone_id", "timestamp", "parameter", "detector_version", name="uq_anomaly"),
                      Index("ix_anomalies_zone_ts", "zone_id", "timestamp"))


class Attribution(Base):
    __tablename__ = "attributions"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(ForeignKey("anomalies.id", ondelete="CASCADE"), index=True)
    contributor_type: Mapped[str] = mapped_column(String(20))  # factory | event
    contributor_id: Mapped[str] = mapped_column(String(80))
    contributor_name: Mapped[str] = mapped_column(String(160))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    correlation: Mapped[float | None] = mapped_column(Float)
    best_lag_windows: Mapped[int | None] = mapped_column(Integer)
    deviation: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(Text)
    time_window_start: Mapped[datetime] = mapped_column(TZ)
    time_window_end: Mapped[datetime] = mapped_column(TZ)
    data_quality: Mapped[dict] = mapped_column(JSONB)
    method_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    parameter: Mapped[str] = mapped_column(String(30))
    generated_at: Mapped[datetime] = mapped_column(TZ)
    based_on_until: Mapped[datetime] = mapped_column(TZ)
    target_time: Mapped[datetime] = mapped_column(TZ)
    prediction: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float] = mapped_column(Float)
    upper_bound: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(40))
    validation_metadata: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (Index("ix_forecasts_zone_param_target", "zone_id", "parameter", "target_time"),)


class Threshold(Base):
    __tablename__ = "thresholds"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"))  # NULL = global rule
    parameter: Mapped[str] = mapped_column(String(30))
    threshold_value: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(8))  # above | below
    persistence_windows: Mapped[int] = mapped_column(Integer, default=1)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(12))
    action_text: Mapped[str] = mapped_column(Text)
    basis: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    parameter: Mapped[str] = mapped_column(String(30))
    threshold_id: Mapped[int] = mapped_column(ForeignKey("thresholds.id"))
    value: Mapped[float] = mapped_column(Float)
    peak_value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(Text)
    source_context: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(12))
    action_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(14))  # active | acknowledged | resolved | dismissed
    episode_open: Mapped[bool] = mapped_column(Boolean, default=True)
    breach_windows: Mapped[int] = mapped_column(Integer)
    first_breach_at: Mapped[datetime] = mapped_column(TZ)
    last_breach_at: Mapped[datetime] = mapped_column(TZ)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZ)
    acknowledged_by: Mapped[str | None] = mapped_column(String(80))
    resolved_at: Mapped[datetime | None] = mapped_column(TZ)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("ix_alerts_zone_status_created", "zone_id", "status", "created_at"),
        # Duplicate-alert prevention enforced by the database: one open episode per rule.
        Index("uq_alerts_open_episode", "zone_id", "parameter", "threshold_id", unique=True,
              postgresql_where=text("episode_open")),
    )


class AlertEvent(Base):
    """Append-only alert log: every create/update/ack/resolve/dispatch is recorded."""
    __tablename__ = "alert_events"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    data_timestamp: Mapped[datetime | None] = mapped_column(TZ)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class FeedbackRecord(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    anomaly_id: Mapped[int | None] = mapped_column(ForeignKey("anomalies.id", ondelete="SET NULL"))
    feedback_type: Mapped[str] = mapped_column(String(30))
    feedback_text: Mapped[str | None] = mapped_column(Text)
    contributor_type: Mapped[str | None] = mapped_column(String(20))
    contributor_id: Mapped[str | None] = mapped_column(String(80))
    operator: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))  # air | water | factory | events | reference
    status: Mapped[str] = mapped_column(String(12))    # HEALTHY | DEGRADED | OFFLINE | SIMULATED
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_successful_fetch: Mapped[datetime | None] = mapped_column(TZ)
    last_attempt: Mapped[datetime | None] = mapped_column(TZ)
    latest_data_timestamp: Mapped[datetime | None] = mapped_column(TZ)
    latency: Mapped[float | None] = mapped_column(Float)  # milliseconds
    records_last_batch: Mapped[int | None] = mapped_column(Integer)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now(), onupdate=func.now())


class PipelineState(Base):
    __tablename__ = "pipeline_state"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now(), onupdate=func.now())
