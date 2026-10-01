// The only module that talks to the backend. No credentials ever live in the frontend.
import type {
  AlertDetail, AnomalyData, AttributionData, DemoStatus, FeedbackItem, FeedbackRequest, ForecastData, Health,
  MapData, ParameterKey, SourceHealthResponse, Summary, TimeRange, TrendData, Zone, Alert,
} from "../types/api";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000/api/v1";
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit, timeout = TIMEOUT_MS): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init, signal: ctrl.signal,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") detail = body.detail;
        else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      } catch { /* non-JSON error body */ }
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError("The server took too long to respond.", 0);
    throw new ApiError("Cannot reach the EnviroPulse API. Check that the backend is running.", 0);
  } finally {
    clearTimeout(timer);
  }
}

const qs = (p: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== null) s.set(k, String(v)); });
  return `?${s.toString()}`;
};

export const api = {
  health: () => request<Health>("/health"),
  sourceHealth: () => request<SourceHealthResponse>("/source-health"),
  zones: () => request<{ zones: Zone[] }>("/zones").then((r) => r.zones),
  summary: (z: string, tr: TimeRange) => request<Summary>(`/zones/${z}/summary${qs({ time_range: tr })}`),
  map: (z: string, p: ParameterKey, tr: TimeRange) => request<MapData>(`/zones/${z}/map${qs({ parameter: p, time_range: tr })}`),
  trends: (z: string, p: ParameterKey, tr: TimeRange) => request<TrendData>(`/zones/${z}/trends${qs({ parameter: p, time_range: tr })}`),
  anomalies: (z: string, p: ParameterKey, tr: TimeRange) => request<AnomalyData>(`/zones/${z}/anomalies${qs({ parameter: p, time_range: tr })}`),
  attribution: (z: string, p: ParameterKey, tr: TimeRange, anomalyId?: number | null) =>
    request<AttributionData>(`/zones/${z}/attribution${qs({ parameter: p, time_range: tr, anomaly_id: anomalyId })}`),
  forecast: (z: string, p: ParameterKey, tr: TimeRange) => request<ForecastData>(`/zones/${z}/forecast${qs({ parameter: p, time_range: tr })}`),
  alerts: (zoneId?: string, status?: string, limit = 50) => request<{ alerts: Alert[] }>(`/alerts${qs({ zone_id: zoneId, status, limit })}`).then((r) => r.alerts),
  alert: (id: number) => request<AlertDetail>(`/alerts/${id}`),
  acknowledge: (id: number, operator: string, note?: string) =>
    request<Alert>(`/alerts/${id}/acknowledge`, { method: "POST", body: JSON.stringify({ operator, note: note || null }) }),
  feedback: (body: FeedbackRequest) => request<FeedbackItem>("/feedback", { method: "POST", body: JSON.stringify(body) }),
  feedbackList: (zoneId: string, limit = 20) => request<{ feedback: FeedbackItem[] }>(`/feedback${qs({ zone_id: zoneId, limit })}`).then((r) => r.feedback),
  demoStatus: () => request<DemoStatus>("/demo/status"),
  demoTick: () => request<{ tick: number; window: string; story: string | null }>("/demo/tick", { method: "POST" }),
  demoOutage: (source: string, enabled: boolean) => request<{ outages: Record<string, boolean> }>("/demo/source-outage", { method: "POST", body: JSON.stringify({ source, enabled }) }),
  demoReset: () => request<unknown>("/demo/reset", { method: "POST" }, 120000),
};
