import { PARAM_OPTIONS, fmtAgo } from "../../format";
import { useDashboardStore } from "../../state/dashboardStore";
import type { ParameterKey, TimeRange } from "../../types/api";
import { SourceHealth } from "../SourceHealth/SourceHealth";
import { ZoneSelector } from "../ZoneSelector/ZoneSelector";

const RANGES: TimeRange[] = ["6h", "24h", "3d", "7d", "14d"];

export function Header() {
  const p = useDashboardStore((s) => s.selectedParameter);
  const setParameter = useDashboardStore((s) => s.setParameter);
  const tr = useDashboardStore((s) => s.timeRange);
  const setTimeRange = useDashboardStore((s) => s.setTimeRange);
  const lastUpdated = useDashboardStore((s) => s.lastUpdated);
  return (
    <header className="header">
      <div className="header-inner">
        <div className="brand">
          <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="7" fill="#1D353B" /><path d="M4 18h6l3-8 5 14 3-6h7" fill="none" stroke="#5FD4C4" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <div>
            <div className="brand-name">EnviroPulse</div>
            <div className="brand-sub">Air and water intelligence for industrial zones</div>
          </div>
        </div>
        <div className="controls">
          <ZoneSelector />
          <div className="control">
            <label htmlFor="param-select">Parameter</label>
            <select id="param-select" className="select" value={p} onChange={(e) => setParameter(e.target.value as ParameterKey)}>
              <optgroup label="Air">{PARAM_OPTIONS.filter((o) => o.domain === "air").map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}</optgroup>
              <optgroup label="Water">{PARAM_OPTIONS.filter((o) => o.domain === "water").map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}</optgroup>
            </select>
          </div>
          <div className="control">
            <span className="label" id="range-label">Time range</span>
            <div className="segmented" role="group" aria-labelledby="range-label">
              {RANGES.map((r) => <button key={r} aria-pressed={tr === r} onClick={() => setTimeRange(r)}>{r}</button>)}
            </div>
          </div>
        </div>
        <div className="header-right">
          <span className="updated">Refreshed {lastUpdated ? fmtAgo(lastUpdated) : "—"}</span>
          <SourceHealth />
        </div>
      </div>
    </header>
  );
}
