import { useEffect, useState } from "react";
import { fmtDateTime, fmtNum } from "../../format";
import { api } from "../../services/api";
import { useDashboardStore } from "../../state/dashboardStore";
import type { AlertDetail } from "../../types/api";

const EVENT_TEXT: Record<string, string> = {
  created: "Created", updated: "Updated", notification_dispatched: "Notified", acknowledged: "Acknowledged",
  resolved: "Resolved", dismissed: "Dismissed", recovery_pending: "Recovering",
};

export function AlertLog() {
  const alerts = useDashboardStore((s) => s.alerts);
  const selected = useDashboardStore((s) => s.selectedAlertId);
  const selectAlert = useDashboardStore((s) => s.selectAlert);
  const token = useDashboardStore((s) => s.refreshToken);
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const active = selected ?? alerts[0]?.id ?? null;
  useEffect(() => {
    if (!active) { setDetail(null); return; }
    let live = true;
    api.alert(active).then((d) => { if (live) setDetail(d); }).catch(() => { if (live) setDetail(null); });
    return () => { live = false; };
  }, [active, token]);
  if (!alerts.length) return <div className="panel-state"><div><strong>No alerts recorded for this zone</strong>Alerts appear here once a threshold breach persists.</div></div>;
  return (
    <div className="split" style={{ gridTemplateColumns: "1.5fr 1fr" }}>
      <div className="scroll">
        <table className="table num">
          <thead><tr><th>#</th><th>Parameter</th><th>Value / threshold</th><th>Severity</th><th>Status</th><th>Breach period</th></tr></thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className={`clickable ${a.id === active ? "sel" : ""}`} onClick={() => selectAlert(a.id)} tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter") selectAlert(a.id); }}>
                <td>{a.id}</td><td>{a.label}</td>
                <td>{fmtNum(a.value, 1)} / {a.threshold} {a.unit}</td>
                <td><span className={`sev ${a.severity}`}>{a.severity}</span></td>
                <td><span className={`status-pill ${a.status}`}>{a.status}</span></td>
                <td>{fmtDateTime(a.first_breach_at)} → {a.episode_open ? "ongoing" : fmtDateTime(a.resolved_at ?? a.last_breach_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="scroll">
        {detail ? (
          <>
            <p className="caption">Alert #{detail.id} history (append-only)</p>
            <ol className="log">
              {detail.log.map((e) => (
                <li key={e.id}><span className="t">{fmtDateTime(e.data_timestamp ?? e.created_at)}</span><span><b>{EVENT_TEXT[e.event_type] ?? e.event_type.replace("feedback_", "Feedback: ")}</b> — {e.message}</span></li>
              ))}
            </ol>
          </>
        ) : <span className="muted small">Select an alert to see its log.</span>}
      </div>
    </div>
  );
}

export function FeedbackHistory() {
  const feedback = useDashboardStore((s) => s.feedback);
  if (!feedback.length) return <p className="small muted" style={{ margin: 0 }}>No operator feedback recorded for this zone yet.</p>;
  return (
    <ol className="log">
      {feedback.map((f) => (
        <li key={f.id}><span className="t">{fmtDateTime(f.created_at)}</span>
          <span><b>{f.feedback_type.replace("_", " ")}</b>{f.alert_id ? ` on alert #${f.alert_id}` : ""}{f.contributor_id ? ` · tagged ${f.contributor_id}` : ""} by {f.operator}{f.feedback_text ? ` — ${f.feedback_text}` : ""}</span></li>
      ))}
    </ol>
  );
}
