// Test fixtures only — never imported by application code.
import type { Alert, Summary } from "../types/api";

export const summaryFixture: Summary = {
  zone_id: "zone_a", zone_name: "Industrial Zone A", last_updated: "2026-09-30T08:35:00Z",
  window: { start: "2026-09-29T08:45:00Z", end: "2026-09-30T08:30:00Z", time_range: "24h", anchor: "latest_zone_data", window_minutes: 15 },
  aqi: { value: 142, category: "Moderate", dominant_parameter: "pm25", timestamp: "2026-09-30T08:30:00Z", source: "zone_mean", method: "Indicative, not an official AQI", status: "OK" },
  water: { status: "Within limits", method: "m", is_simulated: true, parameters: [
    { parameter: "ph", label: "pH", value: 7.4, unit: "pH", status: "within_limits", limits: "6.5–8.5", timestamp: null }] },
  active_anomalies: 3, active_anomaly_definition: "d", anomalies_in_range: 9, active_alerts: 2, acknowledged_alerts: 1,
  threshold_decisions: [], data_quality: { VALID: 10 }, pipeline: [],
};

export const alertFixture: Alert = {
  id: 7, zone_id: "zone_a", zone_name: "Industrial Zone A", parameter: "pm25", label: "PM2.5", value: 86.2, peak_value: 87.1,
  threshold: 60, unit: "µg/m³", direction: "above", severity: "high",
  reason: "PM2.5 zone mean 86.20 µg/m³ exceeded the 60 µg/m³ threshold for 3 consecutive windows.",
  source_context: "Likely contributors (estimate, not proof of cause): Apex Organics (0.98).",
  action_text: "Inspect stack emissions at nearby facilities", status: "active", episode_open: true, breach_windows: 3,
  first_breach_at: "2026-09-30T06:45:00Z", last_breach_at: "2026-09-30T07:15:00Z", acknowledged_at: null, acknowledged_by: null,
  resolved_at: null, created_at: "2026-09-30T07:20:00Z", updated_at: "2026-09-30T07:20:00Z",
};
