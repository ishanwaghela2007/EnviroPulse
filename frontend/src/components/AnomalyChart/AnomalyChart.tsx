import { EChart } from "../../charts/EChart";
import { C, baseOption } from "../../charts/base";
import { fmtNum } from "../../format";
import type { AnomalyData } from "../../types/api";

export function AnomalyChart({ data, selectedId, onSelect }: { data: AnomalyData; selectedId: number | null; onSelect: (id: number) => void }) {
  const base = baseOption();
  const k = data.detector.k;
  const option = {
    ...base,
    yAxis: { ...base.yAxis, name: `${data.label} (${data.unit})`, scale: true },
    legend: { ...base.legend, data: [`Normal band (±${k}σ)`, "Rolling baseline", "Observed", "Anomaly"] },
    tooltip: { ...base.tooltip, valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmtNum(v, 2)) },
    series: [
      { name: "band-low", type: "line", stack: "band", showSymbol: false, lineStyle: { opacity: 0 }, tooltip: { show: false },
        data: data.series.map((p) => [p.timestamp, p.baseline_low]) },
      { name: `Normal band (±${k}σ)`, type: "line", stack: "band", showSymbol: false, lineStyle: { opacity: 0 },
        areaStyle: { color: "rgba(15,110,116,0.13)" }, itemStyle: { color: "rgba(15,110,116,0.35)" },
        tooltip: { show: false },
        data: data.series.map((p) => [p.timestamp, p.baseline_high !== null && p.baseline_low !== null ? p.baseline_high - p.baseline_low : null]) },
      { name: "Rolling baseline", type: "line", showSymbol: false, connectNulls: false,
        lineStyle: { width: 1.2, type: "dashed", color: C.teal }, itemStyle: { color: C.teal },
        data: data.series.map((p) => [p.timestamp, p.rolling_mean]) },
      { name: "Observed", type: "line", showSymbol: false, connectNulls: false, lineStyle: { width: 2, color: C.ink },
        itemStyle: { color: C.ink }, data: data.series.map((p) => [p.timestamp, p.value]) },
      { name: "Anomaly", type: "scatter", z: 10, cursor: "pointer",
        symbolSize: (_: unknown, p: { data: { id: number } }) => (p.data.id === selectedId ? 16 : 11),
        itemStyle: { color: C.anomaly, borderColor: "#fff", borderWidth: 1.5 },
        tooltip: { trigger: "item", formatter: (p: { data: { value: [string, number]; z: number } }) =>
          `Anomaly: ${fmtNum(p.data.value[1], 2)} ${data.unit}<br/>score ${fmtNum(p.data.z, 1)}σ — click to explain` },
        data: data.anomalies.map((a) => ({ value: [a.timestamp, a.value], id: a.id, z: a.score })) },
    ],
  };
  return <EChart className="chart" option={option}
    onEvents={{ click: (p: { seriesName: string; data: { id: number } }) => { if (p.seriesName === "Anomaly") onSelect(p.data.id); } }} />;
}
