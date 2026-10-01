import { useEffect } from "react";
import { api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";

/** Lifecycle step 2: load zones once, then select Industrial Zone A (golden scenario) or the first zone. */
export function useZones() {
  const refreshToken = useDashboardStore((s) => s.refreshToken);
  useEffect(() => {
    const { set, setError, selectedZoneId, setZone } = useDashboardStore.getState();
    api.zones().then((zones) => {
      set({ zones });
      setError("global", null);
      if (!selectedZoneId && zones.length) setZone(zones.find((z) => z.id === "zone_a")?.id ?? zones[0].id);
    }).catch((e) => setError("global", e.message));
  }, [refreshToken]);
}
