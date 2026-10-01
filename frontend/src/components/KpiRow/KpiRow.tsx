import { AQI_COLORS, AQI_TEXT, fmtDateTime, fmtNum } from "../../format";
import type { Summary } from "../../types/api";

/** Four KPIs, every value straight from GET /zones/{id}/summary. */
export function KpiRow({ summary }: { summary: Summary | null }) {
  if (!summary) {
    return <div className="kpis" aria-busy>{["Air quality index", "Water status", "Active anomalies", "Active alerts"].map((l) => (
      <div className="kpi" key={l}><span className="k-label">{l}</span><span className="k-value muted">—</span></div>))}</div>;
  }
  const { aqi, water } = summary;
  const outside = water.parameters.filter((p) => p.status === "outside_limits");
  return (
    <div className="kpis">
      <div className="kpi" data-testid="kpi-aqi">
        <span className="k-label">Air quality index (indicative)</span>
        {aqi.status === "OK" ? (
          <>
            <span className="k-value num">{aqi.value}</span>
            <span className="k-sub">
              <span className="aqi-chip" style={{ background: AQI_COLORS[aqi.category ?? ""], color: AQI_TEXT[aqi.category ?? ""] }}>{aqi.category}</span>
              {" "}dominant {aqi.dominant_parameter?.toUpperCase().replace("PM25", "PM2.5")} · {fmtDateTime(aqi.timestamp)}
            </span>
          </>
        ) : <><span className="k-value muted">—</span><span className="k-sub">No recent air data</span></>}
      </div>
      <div className="kpi" data-testid="kpi-water">
        <span className="k-label">Water status {water.is_simulated && <span className="badge sim">SIMULATED DEMO STREAM</span>}</span>
        <span className="k-value" style={{ fontSize: 24, color: water.status === "Outside limits" ? "var(--alert)" : water.status === "No data" ? "var(--muted)" : "var(--ok)" }}>{water.status}</span>
        <span className="k-sub num">
          {outside.length ? outside.map((p) => `${p.label} ${fmtNum(p.value, 2)} ${p.unit}`).join(" · ")
            : water.parameters.map((p) => `${p.label} ${fmtNum(p.value, p.unit === "pH" ? 2 : 1)} ${p.unit === "pH" ? "" : p.unit}`).join(" · ")}
        </span>
      </div>
      <div className="kpi" data-testid="kpi-anomalies">
        <span className="k-label">Active anomalies</span>
        <span className="k-value num" style={{ color: summary.active_anomalies ? "var(--anomaly)" : undefined }}>{summary.active_anomalies}</span>
        <span className="k-sub">{summary.anomalies_in_range} in selected range · latest hour of data</span>
      </div>
      <div className="kpi" data-testid="kpi-alerts">
        <span className="k-label">Active alerts</span>
        <span className="k-value num" style={{ color: summary.active_alerts ? "var(--alert)" : undefined }}>{summary.active_alerts}</span>
        <span className="k-sub">{summary.acknowledged_alerts} acknowledged and still open</span>
      </div>
    </div>
  );
}
