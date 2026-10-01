import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

export function useMapData() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const p = useDashboardStore((s) => s.selectedParameter);
  const tr = useDashboardStore((s) => s.timeRange);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("map", "mapData", () => (zone ? api.map(zone, p, tr) : null), [zone, p, tr, token]);
}
