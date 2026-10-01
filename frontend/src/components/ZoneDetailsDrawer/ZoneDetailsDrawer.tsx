import { useEffect } from "react";
import { fmtDateTime, fmtNum } from "../../format";
import { useDashboardStore } from "../../state/dashboardStore";

export function ZoneDetailsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const summary = useDashboardStore((s) => s.dashboardSummary);
  const mapData = useDashboardStore((s) => s.mapData);
  const zones = useDashboardStore((s) => s.zones);
  const zoneId = useDashboardStore((s) => s.selectedZoneId);
  const zone = zones.find((z) => z.id === zoneId);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  if (!open || !zone) return null;
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`${zone.name} details`}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
          <div><h2>{zone.name}</h2><div className="muted">{zone.description}</div></div>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
        <p className="small" style={{ background: "var(--water-soft)", padding: "8px 10px", borderRadius: 5 }}>{zone.boundary_note}</p>
        <h3>Water parameters (latest window)</h3>
        <table className="table num"><tbody>
          {summary?.water.parameters.map((p) => (
            <tr key={p.parameter}><td>{p.label}</td><td>{fmtNum(p.value, p.unit === "pH" ? 2 : 1)} {p.unit}</td><td>{p.status.replace("_", " ")}</td><td className="muted">{p.limits}</td></tr>
          ))}
        </tbody></table>
        <p className="small muted">{summary?.water.method}</p>
        <h3>Assets</h3>
        <p className="small">{mapData?.sensors.filter((s) => s.type === "air").length ?? 0} air sensors, {mapData?.sensors.filter((s) => s.type === "water").length ?? 0} water sensors, {mapData?.factories.length ?? 0} factories, {mapData?.events.length ?? 0} events in the selected range.</p>
        <h3>Data quality in selected range</h3>
        <p className="small num">{Object.entries(summary?.data_quality ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "No readings"}</p>
        <h3>AQI method</h3>
        <p className="small">{summary?.aqi.method}</p>
        <h3>Analysis window</h3>
        <p className="small">{fmtDateTime(summary?.window.start)} → {fmtDateTime(summary?.window.end)}. Ranges end at the zone's newest data, not the wall clock, so a paused feed is never shown as current.</p>
      </aside>
    </>
  );
}
