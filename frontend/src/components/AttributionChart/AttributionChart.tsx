import { EChart } from "../../charts/EChart";
import { C, FONT } from "../../charts/base";
import { fmtNum } from "../../format";
import type { AttributionData } from "../../types/api";

/** Likely contributors as ranked ESTIMATES, plus the factory-vs-pollutant association scatter. */
export function AttributionChart({ data }: { data: AttributionData }) {
  const contributors = [...data.contributors].reverse();
  const bars = {
    animation: false, textStyle: { fontFamily: FONT, color: C.ink },
    grid: { left: 8, right: 44, top: 8, bottom: 24, containLabel: true },
    tooltip: { trigger: "item", backgroundColor: "#fff", borderColor: C.line, textStyle: { color: C.ink, fontSize: 12 },
      formatter: (p: { dataIndex: number }) => { const c = contributors[p.dataIndex]; return `<b>${c.contributor_name}</b><br/>estimate score ${fmtNum(c.score, 2)}<br/><span style="white-space:normal">${c.evidence}</span>`; },
      extraCssText: "max-width:320px;white-space:normal" },
    xAxis: { type: "value", min: 0, max: 1, axisLabel: { color: C.muted, fontSize: 11 }, splitLine: { lineStyle: { color: "#EDF2F1" } },
             name: "Estimate score", nameLocation: "middle", nameGap: 22, nameTextStyle: { color: C.muted, fontSize: 11 } },
    yAxis: { type: "category", data: contributors.map((c) => c.contributor_name.replace(" (fictional)", "").slice(0, 34)),
             axisLabel: { color: C.ink, fontSize: 11, width: 150, overflow: "truncate" }, axisTick: { show: false }, axisLine: { lineStyle: { color: C.line } } },
    series: [{ type: "bar", barMaxWidth: 16,
      data: contributors.map((c) => ({ value: c.score, itemStyle: { color: c.contributor_type === "factory" ? C.air : C.anomaly, borderRadius: [0, 3, 3, 0] } })),
      label: { show: true, position: "right", fontSize: 11, color: C.ink, formatter: (p: { value: number }) => fmtNum(p.value, 2) } }],
  };
  const sc = data.scatter;
  const scatter = sc && {
    animation: false, textStyle: { fontFamily: FONT, color: C.ink },
    grid: { left: 44, right: 12, top: 12, bottom: 38 },
    tooltip: { trigger: "item", backgroundColor: "#fff", borderColor: C.line, textStyle: { color: C.ink, fontSize: 12 },
      formatter: (p: { value: [number, number] }) => `${fmtNum(p.value[0], 1)} ${sc.x_unit} → ${fmtNum(p.value[1], 1)} ${sc.y_unit}` },
    xAxis: { type: "value", scale: true, name: `Output t-${sc.lag_windows} (${sc.x_unit})`, nameLocation: "middle", nameGap: 24,
             nameTextStyle: { color: C.muted, fontSize: 11 }, axisLabel: { color: C.muted, fontSize: 10 }, splitLine: { lineStyle: { color: "#EDF2F1" } } },
    yAxis: { type: "value", scale: true, name: sc.y_unit, nameTextStyle: { color: C.muted, fontSize: 11 }, axisLabel: { color: C.muted, fontSize: 10 },
             splitLine: { lineStyle: { color: "#EDF2F1" } } },
    series: [
      { type: "scatter", symbolSize: 6, itemStyle: { color: "rgba(168,98,0,0.45)" }, data: sc.points.filter((p) => !p.is_anomaly_window).map((p) => [p.x, p.y]) },
      { type: "scatter", symbolSize: 13, itemStyle: { color: C.anomaly, borderColor: "#fff", borderWidth: 1.5 }, data: sc.points.filter((p) => p.is_anomaly_window).map((p) => [p.x, p.y]) },
    ],
  };
  return (
    <div className="split">
      <div>
        <p className="caption">Likely contributors <span className="badge estimate">ESTIMATE</span></p>
        <EChart style={{ height: 210 }} option={bars} />
        <ol className="evidence">
          {data.contributors.slice(0, 3).map((c) => (
            <li key={c.rank}><span className="r">{c.rank}</span><span><b>{c.contributor_name}</b> — {c.evidence}</span></li>
          ))}
        </ol>
      </div>
      <div>
        {sc ? (
          <>
            <p className="caption">{sc.factory_name.replace(" (fictional)", "")} output vs {sc.y_label}</p>
            <EChart style={{ height: 230 }} option={scatter!} />
            <p className="small" style={{ margin: "4px 0 0", fontWeight: 600 }}>{sc.caption}</p>
            <p className="small muted" style={{ margin: "2px 0 0" }}>Violet point: the anomaly window. r = {fmtNum(sc.correlation, 2)} over {sc.points.length} aligned windows.</p>
          </>
        ) : <div className="panel-state"><div><strong>No factory association</strong>No factory candidate has enough aligned data for a scatter view.</div></div>}
      </div>
    </div>
  );
}
