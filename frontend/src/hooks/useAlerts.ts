import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

export function useAlerts() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("alerts", "alerts", () => (zone ? api.alerts(zone, undefined, 50) : null), [zone, token]);
  useZoneResource("feedback", "feedback", () => (zone ? api.feedbackList(zone, 20) : null), [zone, token]);
}
