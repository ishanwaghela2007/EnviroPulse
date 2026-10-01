import { useEffect } from "react";
import { ApiError } from "../services/api";
import { type DashboardState, type SliceKey, useDashboardStore } from "../state/dashboardStore";

/** Fetch one dashboard slice whenever its dependencies (zone, parameter, time range, refresh token) change.
 *  On failure the previous valid data is kept and an error message is shown next to the panel. */
export function useZoneResource<T>(slice: SliceKey, field: keyof DashboardState, fetcher: () => Promise<T> | null,
                                   deps: unknown[]): void {
  const { setLoading, setError, set } = useDashboardStore.getState();
  useEffect(() => {
    const p = fetcher();
    if (!p) return;
    let cancelled = false;
    setLoading(slice, true);
    p.then((data) => {
      if (cancelled) return;
      set({ [field]: data, lastUpdated: new Date().toISOString() } as Partial<DashboardState>);
      setError(slice, null);
    }).catch((e: unknown) => {
      if (!cancelled) setError(slice, e instanceof ApiError ? e.message : "Unexpected error while loading data.");
    }).finally(() => { if (!cancelled) setLoading(slice, false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
