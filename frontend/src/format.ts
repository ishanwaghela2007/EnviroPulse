// Display formatting only — no analytical calculation happens in the frontend.
const tf = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
const dtf = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
const tz = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(new Date()).find((p) => p.type === "timeZoneName")?.value ?? "";

export const fmtTime = (iso: string | null | undefined) => (iso ? tf.format(new Date(iso)) : "—");
export const fmtDateTime = (iso: string | null | undefined) => (iso ? dtf.format(new Date(iso)) : "—");
export const tzLabel = tz;
export function fmtNum(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
export function fmtAgo(iso: string | null | undefined) {
  if (!iso) return "never";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
export const PARAM_OPTIONS: { key: import("./types/api").ParameterKey; label: string; domain: "air" | "water" }[] = [
  { key: "pm25", label: "PM2.5", domain: "air" }, { key: "pm10", label: "PM10", domain: "air" },
  { key: "no2", label: "NO₂", domain: "air" }, { key: "turbidity", label: "Turbidity", domain: "water" },
  { key: "dissolved_oxygen", label: "Dissolved oxygen", domain: "water" }, { key: "ph", label: "pH", domain: "water" },
];
export const AQI_COLORS: Record<string, string> = {
  Good: "var(--aqi-good)", Satisfactory: "var(--aqi-sat)", Moderate: "var(--aqi-mod)", Poor: "var(--aqi-poor)",
  "Very poor": "var(--aqi-vpoor)", Severe: "var(--aqi-severe)",
};
export const AQI_TEXT: Record<string, string> = { Good: "#fff", Satisfactory: "#13262B", Moderate: "#13262B", Poor: "#13262B", "Very poor": "#fff", Severe: "#fff" };
export const EVENT_LABEL: Record<string, string> = {
  construction: "Construction", traffic_event: "Traffic event", local_event: "Local event", industrial_activity: "Industrial activity",
};
