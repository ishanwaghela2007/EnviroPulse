import { useEffect, useRef, useState } from "react";
import { api } from "../../services/api";
import { useDashboardStore } from "../../state/dashboardStore";
import type { DemoStatus } from "../../types/api";

/** Controls for the SIMULATED DEMO STREAM. Each action calls the backend, which moves real records
 *  through ingestion → validation → alignment → analytics → alerts. Nothing here animates values. */
export function DemoDock({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const health = useDashboardStore((s) => s.health);
  const token = useDashboardStore((s) => s.refreshToken);
  const requestRefresh = useDashboardStore((s) => s.requestRefresh);
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const playing = useRef(false);

  useEffect(() => { if (health?.demo_controls_enabled) api.demoStatus().then(setStatus).catch(() => undefined); }, [health?.demo_controls_enabled, token]);
  if (!health?.demo_controls_enabled) return null;
  if (!open) return <button className="btn dock-mini" onClick={onToggle}>Show demo controls</button>;

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label); setError(null);
    try { await fn(); setStatus(await api.demoStatus()); requestRefresh(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  };
  const play = async () => {
    playing.current = true; setBusy("play"); setError(null);
    try {
      let s = await api.demoStatus();
      while (playing.current && (s.tick ?? 0) < (s.golden_ticks ?? 12)) {
        await api.demoTick();
        s = await api.demoStatus(); setStatus(s); requestRefresh();
        await new Promise((r) => setTimeout(r, 2500));
      }
    } catch (e) { setError((e as Error).message); }
    finally { playing.current = false; setBusy(null); }
  };
  const tick = status?.tick ?? 0, total = status?.golden_ticks ?? 12;
  const airOut = !!status?.outages?.sim_air;
  const storyText = `Window ${tick}${tick >= total ? " (scenario complete)" : ""} — ${status?.last_step ?? "history loaded, stream not started."}`;
  return (
    <aside className="dock" aria-label="Demo stream controls">
      <div className="dock-inner">
        <span className="dock-title"><span className="sim-tag">SIMULATED DEMO STREAM</span><b>Golden scenario</b></span>
        <div className="progress" role="img" aria-label={`Window ${tick} of ${total}`}>{Array.from({ length: total }, (_, i) => <i key={i} className={i < tick ? "on" : ""} />)}</div>
        <div className="story" title={`${storyText}${status?.next_step ? ` Next: ${status.next_step}` : ""}`}>
          <b>{storyText}</b>{status?.next_step && <span className="next"> Next: {status.next_step}</span>}
        </div>
        <div className="dock-actions">
          <button className="btn primary" disabled={!!busy} onClick={() => act("tick", api.demoTick)}>{busy === "tick" ? "Processing…" : "Advance one window"}</button>
          {busy === "play" ? <button className="btn" onClick={() => { playing.current = false; }}>Pause</button>
            : <button className="btn" disabled={!!busy || tick >= total} onClick={play}>Play scenario</button>}
          <button className="btn" disabled={!!busy} onClick={() => { if (confirm("Reset all data and replay the golden scenario from the start? This takes about 40 seconds.")) act("reset", api.demoReset); }}>
            {busy === "reset" ? "Resetting…" : "Reset"}
          </button>
          <button className="btn" aria-pressed={airOut} disabled={!!busy} title={status?.clock}
                  onClick={() => act("outage", () => api.demoOutage("sim_air", !airOut))}>
            {busy === "outage" ? "Updating…" : airOut ? "End air feed outage" : "Simulate air feed outage"}
          </button>
          <button className="btn" onClick={onToggle} aria-label="Hide demo controls">Hide</button>
        </div>
        {error && <div className="dock-err" role="alert">{error}</div>}
      </div>
    </aside>
  );
}
