import { useDashboardStore } from "../../state/dashboardStore";

export function ZoneSelector() {
  const zones = useDashboardStore((s) => s.zones);
  const selected = useDashboardStore((s) => s.selectedZoneId);
  const setZone = useDashboardStore((s) => s.setZone);
  return (
    <div className="control">
      <label htmlFor="zone-select">Industrial zone</label>
      <select id="zone-select" className="select" value={selected ?? ""} onChange={(e) => setZone(e.target.value)}
              disabled={!zones.length}>
        {!zones.length && <option value="">Loading zones…</option>}
        {zones.map((z) => (
          <option key={z.id} value={z.id}>{z.name}{z.open_alerts ? ` · ${z.open_alerts} open alert${z.open_alerts > 1 ? "s" : ""}` : ""}</option>
        ))}
      </select>
    </div>
  );
}
