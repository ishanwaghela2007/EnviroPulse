import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

export function useForecast() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const p = useDashboardStore((s) => s.selectedParameter);
  const tr = useDashboardStore((s) => s.timeRange);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("forecast", "forecastData", () => (zone ? api.forecast(zone, p, tr) : null), [zone, p, tr, token]);
}
