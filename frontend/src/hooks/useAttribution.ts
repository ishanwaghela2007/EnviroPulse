import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

export function useAttribution() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const p = useDashboardStore((s) => s.selectedParameter);
  const tr = useDashboardStore((s) => s.timeRange);
  const anomalyId = useDashboardStore((s) => s.selectedAnomalyId);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("attribution", "attributionData", () => (zone ? api.attribution(zone, p, tr, anomalyId) : null),
    [zone, p, tr, anomalyId, token]);
}
