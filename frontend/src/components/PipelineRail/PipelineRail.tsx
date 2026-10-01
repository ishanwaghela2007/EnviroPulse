import { useDashboardStore } from "../../state/dashboardStore";

const STAGES = [
  { key: "collect", name: "Collect", target: "map" }, { key: "unify", name: "Unify", target: "trend" },
  { key: "detect", name: "Detect", target: "anomaly" }, { key: "explain", name: "Explain", target: "attribution" },
  { key: "predict", name: "Predict", target: "forecast" }, { key: "alert", name: "Alert", target: "alerts" },
] as const;

/** The six-stage workflow with live status from the backend summary; each stage jumps to its panel. */
export function PipelineRail() {
  const summary = useDashboardStore((s) => s.dashboardSummary);
  const byStage = Object.fromEntries((summary?.pipeline ?? []).map((p) => [p.stage, p]));
  return (
    <nav className="rail" aria-label="Pipeline stages">
      <div className="rail-inner">
        {STAGES.map((st, i) => {
          const info = byStage[st.key];
          const status = info?.status ?? "no_data";
          const cls = st.key === "alert" && status === "attention" ? "alert-attn" : status;
          return (
            <button key={st.key} className={`stage ${cls}`}
                    onClick={() => document.getElementById(st.target)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
              <span className="n" aria-hidden>{i + 1}</span>
              <span className="name">{st.name}</span>
              <span className="detail">{info?.detail ?? "Waiting for data"}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
