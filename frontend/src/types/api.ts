// Mirrors backend/app/models/schemas.py. Units always come from the API; the UI never infers them.
export type ParameterKey = "pm25" | "pm10" | "no2" | "ph" | "turbidity" | "dissolved_oxygen";
export type TimeRange = "1h" | "6h" | "12h" | "24h" | "3d" | "7d" | "14d";
export type SourceStatus = "HEALTHY" | "DEGRADED" | "OFFLINE" | "SIMULATED";

export interface Window { start: string; end: string; time_range: string | null; anchor: "latest_zone_data" | "explicit"; window_minutes: number }

export interface Health {
  status: "ok" | "degraded"; server_time: string;
  api: { status: string }; database: { status: string; detail: Record<string, unknown> };
  redis: { status: string }; scheduler: { status: string };
  data_version: number | null; latest_data_timestamp: string | null; demo_controls_enabled: boolean;
}

export interface SourceHealthItem {
  source_name: string; label: string; category: string; status: SourceStatus; is_simulated: boolean;
  last_successful_fetch: string | null; last_attempt: string | null; latest_data_timestamp: string | null;
  latency_ms: number | null; records_last_batch: number | null; consecutive_failures: number;
  error_message: string | null; last_known_good: Record<string, unknown> | null;
}
export interface SourceHealthResponse { sources: SourceHealthItem[]; counts: Record<string, number>; simulated_label: string }

export interface Zone {
  id: string; name: string; description: string | null; status: string; boundary_note: string | null;
  geometry: GeoJSON.Polygon; centroid: { lat: number; lon: number }; latest_aqi: number | null;
  aqi_category: string | null; open_alerts: number; last_data_timestamp: string | null;
}

export interface ThresholdDecision {
  threshold_id: number; parameter: ParameterKey; label: string; unit: string; threshold: number;
  direction: "above" | "below"; persistence_windows: number; min_confidence: number; severity: string; basis: string;
  current_value: number | null; confidence: number | null; consecutive_breach_windows: number; evaluated_at: string | null;
  decision: "within_limits" | "pending_persistence" | "alert_open" | "insufficient_data"; open_alert_id: number | null;
}
export interface PipelineStage { stage: "collect" | "unify" | "detect" | "explain" | "predict" | "alert"; status: "ok" | "attention" | "no_data" | "degraded"; detail: string }
export interface WaterParam { parameter: ParameterKey; label: string; value: number | null; unit: string; status: "within_limits" | "outside_limits" | "no_data"; limits: string; timestamp: string | null }
export interface Summary {
  zone_id: string; zone_name: string; window: Window; last_updated: string | null;
  aqi: { value: number | null; category: string | null; dominant_parameter: string | null; timestamp: string | null; source: string | null; method: string | null; status: "OK" | "NO_DATA" };
  water: { status: "Within limits" | "Outside limits" | "No data"; method: string; parameters: WaterParam[]; is_simulated: boolean };
  active_anomalies: number; active_anomaly_definition: string; anomalies_in_range: number;
  active_alerts: number; acknowledged_alerts: number; threshold_decisions: ThresholdDecision[];
  data_quality: Record<string, number>; pipeline: PipelineStage[];
}

export interface LatestValue { parameter: ParameterKey; label: string; value: number | null; unit: string; timestamp: string; quality_flag: string; quality_reason: string | null }
export interface MapSensor { id: string; type: "air" | "water"; name: string; lat: number; lon: number; source: string; is_simulated: boolean; latest: LatestValue[] }
export interface MapFactory { id: string; name: string; sector: string; status: string; lat: number; lon: number; latest_output: { value: number; unit: string; timestamp: string; operating_state: string } | null; output_trend: { timestamp: string; value: number | null }[] }
export interface MapEvent { id: number; type: string; start_time: string; end_time: string | null; severity: string; description: string; lat: number; lon: number; source: string; active_at_latest: boolean }
export interface MapData { zone_id: string; zone: Zone; window: Window; parameter: ParameterKey; sensors: MapSensor[]; factories: MapFactory[]; events: MapEvent[]; intensity: { sensor_id: string; lat: number; lon: number; value: number; unit: string; level: number }[]; intensity_note: string }

export interface SeriesPoint { timestamp: string; value: number | null; valid_sensors?: number | null; confidence?: number | null }
export interface EventMarker { id: number; type: string; start_time: string; end_time: string | null; severity: string; description: string }
export interface TrendData { zone_id: string; parameter: ParameterKey; label: string; unit: string; window: Window; series: SeriesPoint[]; missing_windows: number; factory_series: { factory_id: string; name: string; unit: string; points: SeriesPoint[] }[]; event_markers: EventMarker[]; quality_counts: Record<string, number>; source_label: string }

export interface AnomalyItem { id: number; timestamp: string; parameter: ParameterKey; value: number; score: number; direction: string; baseline_mean: number; baseline_low: number; baseline_high: number; reason: string; detector_version: string; attribution_count: number }
export interface AnomalyData { zone_id: string; parameter: ParameterKey; label: string; unit: string; window: Window; status: "OK" | "INSUFFICIENT_HISTORY" | "NO_DATA"; detector: { method: string; version: string; k: number; baseline_windows: number }; series: { timestamp: string; value: number | null; rolling_mean: number | null; baseline_low: number | null; baseline_high: number | null; score: number | null }[]; anomalies: AnomalyItem[]; note: string }

export interface Contributor { rank: number; contributor_type: "factory" | "event"; contributor_id: string; contributor_name: string; score: number; correlation: number | null; best_lag_windows: number | null; deviation: number | null; evidence: string; time_window_start: string; time_window_end: string; data_quality: Record<string, number>; method_version: string }
export interface AttributionData { zone_id: string; status: "OK" | "NO_ANOMALY_IN_RANGE" | "ANOMALY_NOT_FOUND"; label: "ESTIMATE"; disclaimer: string; method: string; method_version: string; anomaly: AnomalyItem | null; contributors: Contributor[]; scatter: { factory_id: string; factory_name: string; x_label: string; x_unit: string; y_label: string; y_unit: string; lag_windows: number; correlation: number | null; caption: string; points: { timestamp: string; x: number; y: number; is_anomaly_window: boolean }[] } | null; unavailable_context: { variable: string; status: string; reason: string }[]; message?: string | null }

export interface ForecastData { zone_id: string; parameter: ParameterKey; label: string; unit: string; status: "OK" | "INSUFFICIENT_HISTORY" | "INSUFFICIENT_RECENT_DATA" | "MODEL_ERROR"; message?: string | null; horizon_windows: number; window_minutes: number; model?: string | null; model_version?: string | null; generated_at?: string | null; based_on_until?: string | null; validation?: { mae: number; rmse: number; selected_model: string; holdout_windows: number; train_windows: number; candidates: Record<string, { mae: number; rmse: number }>; band: string; method: string } | null; points: { target_time: string; prediction: number; lower_bound: number; upper_bound: number }[]; risk?: { level: string; message: string; threshold?: number; first_time?: string } | null; history: SeriesPoint[]; observed_windows?: number | null; required_windows?: number | null }

export interface Alert { id: number; zone_id: string; zone_name: string; parameter: ParameterKey; label: string; value: number; peak_value: number; threshold: number; unit: string; direction: string; severity: string; reason: string; source_context: string | null; action_text: string; status: "active" | "acknowledged" | "resolved" | "dismissed"; episode_open: boolean; breach_windows: number; first_breach_at: string; last_breach_at: string; acknowledged_at: string | null; acknowledged_by: string | null; resolved_at: string | null; created_at: string; updated_at: string }
export interface AlertLogEntry { id: number; event_type: string; message: string; value: number | null; data_timestamp: string | null; created_at: string }
export interface AlertDetail extends Alert { log: AlertLogEntry[] }

export type FeedbackType = "confirm" | "dismiss" | "false_positive" | "tag_factory" | "tag_event" | "sensor_issue" | "note";
export interface FeedbackRequest { zone_id: string; alert_id?: number | null; anomaly_id?: number | null; feedback_type: FeedbackType; feedback_text?: string | null; contributor_id?: string | null; operator?: string }
export interface FeedbackItem { id: number; zone_id: string; alert_id: number | null; anomaly_id: number | null; feedback_type: FeedbackType; feedback_text: string | null; contributor_type: string | null; contributor_id: string | null; operator: string | null; created_at: string }

export interface DemoStatus { initialised: boolean; tick?: number; next_window?: string; golden_ticks?: number; golden_complete?: boolean; last_step?: string | null; next_step?: string | null; outages?: Record<string, boolean>; label?: string; clock?: string }
