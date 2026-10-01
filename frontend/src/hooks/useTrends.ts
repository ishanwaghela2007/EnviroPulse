import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

export function useTrends() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const p = useDashboardStore((s) => s.selectedParameter);
  const tr = useDashboardStore((s) => s.timeRange);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("trends", "trendData", () => (zone ? api.trends(zone, p, tr) : null), [zone, p, tr, token]);
}
