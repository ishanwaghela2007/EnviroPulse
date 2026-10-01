import { useState } from "react";
import { fmtDateTime, fmtNum } from "../../format";
import { api } from "../../services/api";
import { useDashboardStore } from "../../state/dashboardStore";
import type { Alert, FeedbackType, ThresholdDecision } from "../../types/api";

const DECISION_TEXT: Record<ThresholdDecision["decision"], string> = {
  within_limits: "Within limits", pending_persistence: "Breach, awaiting persistence", alert_open: "Alert open",
  insufficient_data: "Insufficient data",
};
const FEEDBACK_TYPES: { v: FeedbackType; l: string }[] = [
  { v: "confirm", l: "Confirm alert is valid" }, { v: "false_positive", l: "Mark as false positive" },
  { v: "dismiss", l: "Dismiss alert" }, { v: "tag_factory", l: "Tag a factory" }, { v: "tag_event", l: "Tag an event" },
  { v: "sensor_issue", l: "Report sensor issue" }, { v: "note", l: "Add a note" },
];

export function AlertCard({ alert }: { alert: Alert }) {
  const dirWord = alert.direction === "above" ? "above" : "below";
  return (
    <article className={`alert-card ${alert.status}`} aria-label={`Alert ${alert.id}`}>
      <div className="alert-top">
        <span className="alert-title">{alert.label} {dirWord} threshold · {alert.zone_name}</span>
        <span style={{ display: "flex", gap: 6 }}><span className={`sev ${alert.severity}`}>{alert.severity}</span><span className={`status-pill ${alert.status}`}>{alert.status}</span></span>
      </div>
      <dl className="alert-grid num">
        <dt>Zone</dt><dt>Parameter</dt><dt>Current value</dt><dt>Threshold</dt>
        <dd>{alert.zone_name}</dd><dd>{alert.label}</dd>
        <dd style={{ color: "var(--alert)" }}>{fmtNum(alert.value, 2)} {alert.unit}</dd>
        <dd>{dirWord === "above" ? ">" : "<"} {alert.threshold} {alert.unit}</dd>
        <dt>Peak</dt><dt>Breach windows</dt><dt>First breach</dt><dt>Last breach</dt>
        <dd>{fmtNum(alert.peak_value, 2)} {alert.unit}</dd><dd>{alert.breach_windows}</dd>
        <dd>{fmtDateTime(alert.first_breach_at)}</dd><dd>{fmtDateTime(alert.last_breach_at)}</dd>
      </dl>
      <p className="alert-text"><b>Reason.</b> {alert.reason}</p>
      {alert.source_context && <p className="alert-text"><b>Context.</b> {alert.source_context}</p>}
      <p className="alert-text"><b>Recommended action.</b> {alert.action_text}</p>
      {alert.acknowledged_at && <p className="alert-text small muted">Acknowledged by {alert.acknowledged_by} at {fmtDateTime(alert.acknowledged_at)}</p>}
      {alert.resolved_at && <p className="alert-text small muted">Episode closed at {fmtDateTime(alert.resolved_at)}</p>}
    </article>
  );
}

export function AlertPanel() {
  const alerts = useDashboardStore((s) => s.alerts);
  const selectedAlertId = useDashboardStore((s) => s.selectedAlertId);
  const summary = useDashboardStore((s) => s.dashboardSummary);
  const zoneId = useDashboardStore((s) => s.selectedZoneId);
  const mapData = useDashboardStore((s) => s.mapData);
  const attribution = useDashboardStore((s) => s.attributionData);
  const requestRefresh = useDashboardStore((s) => s.requestRefresh);
  const [operator, setOperator] = useState("Duty officer");
  const [note, setNote] = useState("");
  const [fbType, setFbType] = useState<FeedbackType>("confirm");
  const [contributor, setContributor] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const alert = alerts.find((a) => a.id === selectedAlertId) ?? alerts.find((a) => a.episode_open) ?? null;
  const decisions = summary?.threshold_decisions ?? [];
  const needsContributor = fbType === "tag_factory" || fbType === "tag_event";
  const contributorOptions = fbType === "tag_factory"
    ? (mapData?.factories ?? []).map((f) => ({ id: f.id, label: f.name }))
    : (mapData?.events ?? []).map((e) => ({ id: String(e.id), label: e.description }));

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true); setMsg(null);
    try { await fn(); setMsg({ ok: true, text: ok }); setNote(""); requestRefresh(); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    finally { setBusy(false); }
  };

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {alert ? <AlertCard alert={alert} /> : (
        <div className="panel-state" style={{ minHeight: 110 }}><div><strong>No open alerts in this zone</strong>Rules are evaluated on every new window. Past alerts are listed in the alert log.</div></div>
      )}

      {alert && zoneId && (
        <div className="form" aria-label="Operator actions">
          <div className="form-row">
            <input className="input" style={{ flex: 1 }} value={operator} onChange={(e) => setOperator(e.target.value)} aria-label="Operator name" maxLength={80} />
            <button className="btn primary" disabled={busy || alert.status !== "active" || !operator.trim()}
                    onClick={() => run(() => api.acknowledge(alert.id, operator.trim(), note || undefined), "Alert acknowledged and logged.")}>
              Acknowledge alert
            </button>
          </div>
          <div className="form-row">
            <select className="input" value={fbType} onChange={(e) => { setFbType(e.target.value as FeedbackType); setContributor(""); }} aria-label="Feedback type">
              {FEEDBACK_TYPES.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
            </select>
            {needsContributor && (
              <select className="input" style={{ flex: 1 }} value={contributor} onChange={(e) => setContributor(e.target.value)} aria-label="Contributor">
                <option value="">Choose…</option>
                {contributorOptions.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            )}
          </div>
          <textarea className="input" placeholder="Note for the log (optional)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} aria-label="Feedback note" />
          <div className="form-row" style={{ alignItems: "center" }}>
            <button className="btn" disabled={busy || (needsContributor && !contributor) || !operator.trim()}
                    onClick={() => run(() => api.feedback({ zone_id: zoneId, alert_id: alert.id,
                      anomaly_id: attribution?.anomaly?.id ?? null, feedback_type: fbType, feedback_text: note || null,
                      contributor_id: needsContributor ? contributor : null, operator: operator.trim() }), "Feedback saved.")}>
              Save feedback
            </button>
            {msg && <span className={`toast ${msg.ok ? "" : "err"}`} role="status">{msg.text}</span>}
          </div>
        </div>
      )}

      <div>
        <p className="caption">Threshold decisions (latest window)</p>
        <table className="decisions num">
          <thead><tr><th>Rule</th><th>Value</th><th>Persistence</th><th>Decision</th></tr></thead>
          <tbody>
            {decisions.map((d) => (
              <tr key={d.threshold_id} title={d.basis}>
                <td>{d.label} {d.direction === "above" ? ">" : "<"} {d.threshold} {d.unit}</td>
                <td>{fmtNum(d.current_value, d.unit === "pH" ? 2 : 1)}{d.confidence !== null && <span className="muted"> · conf {fmtNum(d.confidence, 2)}</span>}</td>
                <td>
                  {Math.min(d.consecutive_breach_windows, d.persistence_windows)}/{d.persistence_windows}
                  <span className="persist" aria-hidden>{Array.from({ length: d.persistence_windows }, (_, i) => <i key={i} className={i < d.consecutive_breach_windows ? "on" : ""} />)}</span>
                </td>
                <td><span className={`decision ${d.decision}`}>{DECISION_TEXT[d.decision]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small muted" style={{ margin: "6px 0 0" }}>An alert opens only after the breach persists for the required consecutive windows with enough valid sensors. Hover a rule to see its basis.</p>
      </div>
    </div>
  );
}
