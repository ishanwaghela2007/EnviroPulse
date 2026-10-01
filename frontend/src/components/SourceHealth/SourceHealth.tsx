import { useEffect, useRef, useState } from "react";
import { fmtAgo, fmtDateTime, fmtNum } from "../../format";
import { useDashboardStore } from "../../state/dashboardStore";

/** Source freshness and status. Simulated sources are always marked SIMULATED DEMO STREAM. */
export function SourceHealth() {
  const sh = useDashboardStore((s) => s.sourceHealth);
  const health = useDashboardStore((s) => s.health);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const sources = sh?.sources ?? [];
  const problems = sources.filter((s) => s.is_simulated && (s.status === "DEGRADED" || s.status === "OFFLINE"));
  const worst = problems.some((s) => s.status === "OFFLINE") ? "OFFLINE" : problems.length ? "DEGRADED" : "SIMULATED";
  const summary = !sh ? "Checking sources…" : problems.length
    ? `${problems.length} feed${problems.length > 1 ? "s" : ""} ${worst === "OFFLINE" ? "offline" : "degraded"}`
    : "Simulated feeds running";
  return (
    <div ref={ref}>
      <button className="sh-button" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className={`dot ${worst}`} aria-hidden />
        <span>{summary}</span>
        {health && health.status !== "ok" && <span className="badge status-DEGRADED">API degraded</span>}
      </button>
      {open && (
        <div className="sh-pop" role="dialog" aria-label="Source health">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
            <strong>Data sources</strong>
            <span className="small muted">Database {health?.database.status ?? "…"} · Cache {health?.redis.status ?? "…"}</span>
          </div>
          {sources.map((s) => (
            <div className="sh-row" key={s.source_name}>
              <span className={`dot ${s.status}`} style={{ marginTop: 6 }} aria-hidden />
              <div>
                <div style={{ fontWeight: 600 }}>{s.label}</div>
                <div className="sh-meta">
                  Last successful fetch {s.last_successful_fetch ? fmtAgo(s.last_successful_fetch) : "never"}
                  {s.latest_data_timestamp && <> · data up to {fmtDateTime(s.latest_data_timestamp)}</>}
                  {s.latency_ms !== null && <> · latency {fmtNum(s.latency_ms, 0)} ms</>}
                </div>
                {s.error_message && <div className="sh-meta" style={{ color: s.status === "OFFLINE" && !s.is_simulated ? "var(--muted)" : "var(--alert)" }}>{s.error_message}</div>}
                {s.status === "DEGRADED" && s.last_known_good && (
                  <div className="sh-meta">Showing last known good data; nothing new is presented as live.</div>
                )}
              </div>
              <span className={`badge status-${s.status}`}>{s.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
