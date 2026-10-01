"""API schemas (clean contracts; database rows are never returned directly)."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ParameterKey = Literal["pm25", "pm10", "no2", "ph", "turbidity", "dissolved_oxygen"]
TimeRange = Literal["1h", "6h", "12h", "24h", "3d", "7d", "14d"]
AlertStatus = Literal["active", "acknowledged", "resolved", "dismissed", "open"]
FeedbackType = Literal["confirm", "dismiss", "false_positive", "tag_factory", "tag_event", "sensor_issue", "note"]


class ErrorResponse(BaseModel):
    detail: str


class Window(BaseModel):
    start: datetime
    end: datetime
    time_range: str | None = None
    anchor: Literal["latest_zone_data", "explicit"] = Field(
        description="latest_zone_data: the range ends at the zone's newest aligned window (not wall-clock time).")
    window_minutes: int


# ---------------- health ----------------
class ComponentStatus(BaseModel):
    status: str
    detail: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    server_time: datetime
    api: ComponentStatus
    database: ComponentStatus
    redis: ComponentStatus
    scheduler: ComponentStatus
    data_version: int | None = Field(description="Increments whenever the pipeline writes new results; poll to refresh.")
    latest_data_timestamp: datetime | None
    demo_controls_enabled: bool


class SourceHealthItem(BaseModel):
    source_name: str
    label: str
    category: str
    status: Literal["HEALTHY", "DEGRADED", "OFFLINE", "SIMULATED"]
    is_simulated: bool
    last_successful_fetch: datetime | None
    last_attempt: datetime | None
    latest_data_timestamp: datetime | None
    latency_ms: float | None
    records_last_batch: int | None
    consecutive_failures: int
    error_message: str | None
    last_known_good: dict | None = Field(None, description="Last-known-good batch summary from the Redis cache.")


class SourceHealthResponse(BaseModel):
    sources: list[SourceHealthItem]
    counts: dict[str, int]
    simulated_label: str = "SIMULATED DEMO STREAM"


# ---------------- zones ----------------
class ZoneItem(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    boundary_note: str | None
    geometry: dict
    centroid: dict
    latest_aqi: int | None
    aqi_category: str | None
    open_alerts: int
    last_data_timestamp: datetime | None


class ZonesResponse(BaseModel):
    zones: list[ZoneItem]


class AqiBlock(BaseModel):
    value: int | None
    category: str | None
    dominant_parameter: str | None
    timestamp: datetime | None
    source: str | None
    method: str | None
    status: Literal["OK", "NO_DATA"]


class WaterParam(BaseModel):
    parameter: str
    label: str
    value: float | None
    unit: str
    status: Literal["within_limits", "outside_limits", "no_data"]
    limits: str
    timestamp: datetime | None


class WaterBlock(BaseModel):
    status: Literal["Within limits", "Outside limits", "No data"]
    method: str
    parameters: list[WaterParam]
    is_simulated: bool


class ThresholdDecision(BaseModel):
    threshold_id: int
    parameter: str
    label: str
    unit: str
    threshold: float
    direction: str
    persistence_windows: int
    min_confidence: float
    severity: str
    basis: str
    current_value: float | None
    confidence: float | None
    consecutive_breach_windows: int
    evaluated_at: datetime | None
    decision: Literal["within_limits", "pending_persistence", "alert_open", "insufficient_data"]
    open_alert_id: int | None


class PipelineStage(BaseModel):
    stage: Literal["collect", "unify", "detect", "explain", "predict", "alert"]
    status: Literal["ok", "attention", "no_data", "degraded"]
    detail: str


class SummaryResponse(BaseModel):
    zone_id: str
    zone_name: str
    window: Window
    last_updated: datetime | None
    aqi: AqiBlock
    water: WaterBlock
    active_anomalies: int
    active_anomaly_definition: str
    anomalies_in_range: int
    active_alerts: int
    acknowledged_alerts: int
    threshold_decisions: list[ThresholdDecision]
    data_quality: dict[str, int]
    pipeline: list[PipelineStage]


class LatestValue(BaseModel):
    parameter: str
    label: str
    value: float | None
    unit: str
    timestamp: datetime
    quality_flag: str
    quality_reason: str | None


class MapSensor(BaseModel):
    id: str
    type: str
    name: str
    lat: float
    lon: float
    source: str
    is_simulated: bool
    latest: list[LatestValue]


class MapFactory(BaseModel):
    id: str
    name: str
    sector: str
    status: str
    lat: float
    lon: float
    latest_output: dict | None
    output_trend: list[dict]


class MapEvent(BaseModel):
    id: int
    type: str
    start_time: datetime
    end_time: datetime | None
    severity: str
    description: str
    lat: float
    lon: float
    source: str
    active_at_latest: bool


class IntensityPoint(BaseModel):
    sensor_id: str
    lat: float
    lon: float
    value: float
    unit: str
    level: float = Field(description="0..1 relative to the configured threshold for the parameter (1 = at threshold).")


class MapResponse(BaseModel):
    zone_id: str
    zone: dict
    window: Window
    parameter: str
    sensors: list[MapSensor]
    factories: list[MapFactory]
    events: list[MapEvent]
    intensity: list[IntensityPoint]
    intensity_note: str


class SeriesPoint(BaseModel):
    timestamp: datetime
    value: float | None
    valid_sensors: float | None = None
    confidence: float | None = None


class TrendResponse(BaseModel):
    zone_id: str
    parameter: str
    label: str
    unit: str
    window: Window
    series: list[SeriesPoint]
    missing_windows: int
    factory_series: list[dict]
    event_markers: list[dict]
    quality_counts: dict[str, int]
    source_label: str


class AnomalySeriesPoint(BaseModel):
    timestamp: datetime
    value: float | None
    rolling_mean: float | None
    baseline_low: float | None
    baseline_high: float | None
    score: float | None


class AnomalyItem(BaseModel):
    id: int
    timestamp: datetime
    parameter: str
    value: float
    score: float
    direction: str
    baseline_mean: float
    baseline_low: float
    baseline_high: float
    reason: str
    detector_version: str
    attribution_count: int


class AnomaliesResponse(BaseModel):
    zone_id: str
    parameter: str
    label: str
    unit: str
    window: Window
    status: Literal["OK", "INSUFFICIENT_HISTORY", "NO_DATA"]
    detector: dict
    series: list[AnomalySeriesPoint]
    anomalies: list[AnomalyItem]
    note: str


class ContributorItem(BaseModel):
    rank: int
    contributor_type: str
    contributor_id: str
    contributor_name: str
    score: float
    correlation: float | None
    best_lag_windows: int | None
    deviation: float | None
    evidence: str
    time_window_start: datetime
    time_window_end: datetime
    data_quality: dict
    method_version: str


class AttributionResponse(BaseModel):
    zone_id: str
    status: Literal["OK", "NO_ANOMALY_IN_RANGE", "ANOMALY_NOT_FOUND"]
    label: Literal["ESTIMATE"]
    disclaimer: str
    method: str
    method_version: str
    anomaly: AnomalyItem | None
    contributors: list[ContributorItem]
    scatter: dict | None
    unavailable_context: list[dict]
    message: str | None = None


class ForecastPoint(BaseModel):
    target_time: datetime
    prediction: float
    lower_bound: float
    upper_bound: float


class ForecastResponse(BaseModel):
    zone_id: str
    parameter: str
    label: str
    unit: str
    status: Literal["OK", "INSUFFICIENT_HISTORY", "INSUFFICIENT_RECENT_DATA", "MODEL_ERROR"]
    message: str | None = None
    horizon_windows: int
    window_minutes: int
    model: str | None = None
    model_version: str | None = None
    generated_at: datetime | None = None
    based_on_until: datetime | None = None
    validation: dict | None = None
    points: list[ForecastPoint]
    risk: dict | None = None
    history: list[SeriesPoint] = []
    observed_windows: int | None = None
    required_windows: int | None = None


# ---------------- alerts / feedback ----------------
class AlertItem(BaseModel):
    id: int
    zone_id: str
    zone_name: str
    parameter: str
    label: str
    value: float
    peak_value: float
    threshold: float
    unit: str
    direction: str
    severity: str
    reason: str
    source_context: str | None
    action_text: str
    status: str
    episode_open: bool
    breach_windows: int
    first_breach_at: datetime
    last_breach_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertLogEntry(BaseModel):
    id: int
    event_type: str
    message: str
    value: float | None
    data_timestamp: datetime | None
    created_at: datetime


class AlertsResponse(BaseModel):
    alerts: list[AlertItem]
    count: int


class AlertDetailResponse(AlertItem):
    log: list[AlertLogEntry]


class AcknowledgeRequest(BaseModel):
    operator: str = Field("operator", min_length=1, max_length=80)
    note: str | None = Field(None, max_length=2000)


class FeedbackRequest(BaseModel):
    zone_id: str = Field(min_length=1, max_length=40)
    alert_id: int | None = None
    anomaly_id: int | None = None
    feedback_type: FeedbackType
    feedback_text: str | None = Field(None, max_length=2000)
    contributor_id: str | None = Field(None, max_length=80)
    operator: str = Field("operator", min_length=1, max_length=80)


class FeedbackItem(BaseModel):
    id: int
    zone_id: str
    alert_id: int | None
    anomaly_id: int | None
    feedback_type: str
    feedback_text: str | None
    contributor_type: str | None
    contributor_id: str | None
    operator: str | None
    created_at: datetime


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackItem]


# ---------------- demo ----------------
class OutageRequest(BaseModel):
    source: Literal["sim_air", "sim_water", "sim_factory", "sim_events"]
    enabled: bool
