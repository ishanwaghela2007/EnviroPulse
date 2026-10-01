// Shared dashboard state. Every panel reads the same selectedZoneId / selectedParameter / timeRange,
// so selecting a zone anywhere (selector or map) re-synchronises all panels.
import { create } from "zustand";
import type {
  Alert, AnomalyData, AttributionData, FeedbackItem, ForecastData, Health, MapData, ParameterKey, SourceHealthResponse,
  Summary, TimeRange, TrendData, Zone,
} from "../types/api";

export type SliceKey = "summary" | "map" | "trends" | "anomalies" | "attribution" | "forecast" | "alerts" | "feedback";

export interface DashboardState {
  selectedZoneId: string | null;
  selectedParameter: ParameterKey;
  timeRange: TimeRange;
  selectedAnomalyId: number | null;
  selectedAlertId: number | null;

  health: Health | null;
  sourceHealth: SourceHealthResponse | null;
  zones: Zone[];
  dashboardSummary: Summary | null;
  mapData: MapData | null;
  trendData: TrendData | null;
  anomalyData: AnomalyData | null;
  attributionData: AttributionData | null;
  forecastData: ForecastData | null;
  alerts: Alert[];
  feedback: FeedbackItem[];

  loading: Partial<Record<SliceKey, boolean>>;
  errors: Partial<Record<SliceKey | "global", string | null>>;
  lastUpdated: string | null;
  refreshToken: number;

  setZone: (id: string) => void;
  setParameter: (p: ParameterKey) => void;
  setTimeRange: (t: TimeRange) => void;
  selectAnomaly: (id: number | null) => void;
  selectAlert: (id: number | null) => void;
  requestRefresh: () => void;
  set: (partial: Partial<DashboardState>) => void;
  setLoading: (k: SliceKey, v: boolean) => void;
  setError: (k: SliceKey | "global", msg: string | null) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  selectedZoneId: null,
  selectedParameter: "pm25",
  timeRange: "24h",
  selectedAnomalyId: null,
  selectedAlertId: null,
  health: null, sourceHealth: null, zones: [],
  dashboardSummary: null, mapData: null, trendData: null, anomalyData: null, attributionData: null,
  forecastData: null, alerts: [], feedback: [],
  loading: {}, errors: {}, lastUpdated: null, refreshToken: 0,

  setZone: (id) => set({ selectedZoneId: id, selectedAnomalyId: null, selectedAlertId: null }),
  setParameter: (p) => set({ selectedParameter: p, selectedAnomalyId: null }),
  setTimeRange: (t) => set({ timeRange: t, selectedAnomalyId: null }),
  selectAnomaly: (id) => set({ selectedAnomalyId: id }),
  selectAlert: (id) => set({ selectedAlertId: id }),
  requestRefresh: () => set((s) => ({ refreshToken: s.refreshToken + 1 })),
  set: (partial) => set(partial),
  setLoading: (k, v) => set((s) => ({ loading: { ...s.loading, [k]: v } })),
  setError: (k, msg) => set((s) => ({ errors: { ...s.errors, [k]: msg } })),
}));
