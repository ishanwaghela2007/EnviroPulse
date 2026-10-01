import { useEffect, useRef } from "react";
import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";
import { useZoneResource } from "./useZoneResource";

const POLL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 5000);

/** Polls /health and /source-health. When the backend data_version changes (new pipeline results, alert,
 *  feedback), every zone panel is refetched — the dashboard never animates values on its own. */
export function useHealthPolling() {
  const lastVersion = useRef<number | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      const { set, setError, requestRefresh } = useDashboardStore.getState();
      try {
        const [health, sourceHealth] = await Promise.all([api.health(), api.sourceHealth()]);
        if (!alive) return;
        set({ health, sourceHealth });
        setError("global", null);
        if (lastVersion.current !== undefined && health.data_version !== lastVersion.current) requestRefresh();
        lastVersion.current = health.data_version;
      } catch (e) {
        if (alive) setError("global", (e as Error).message);
      }
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);
}

export function useDashboard() {
  const zone = useDashboardStore((s) => s.selectedZoneId);
  const tr = useDashboardStore((s) => s.timeRange);
  const token = useDashboardStore((s) => s.refreshToken);
  useZoneResource("summary", "dashboardSummary", () => (zone ? api.summary(zone, tr) : null), [zone, tr, token]);
}
