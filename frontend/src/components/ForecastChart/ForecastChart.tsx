import { EChart } from "../../charts/EChart";
import { C, baseOption } from "../../charts/base";
import { fmtNum } from "../../format";
import type { ForecastData, ThresholdDecision } from "../../types/api";

export function ForecastChart({ data, thresholds }: { data: ForecastData; thresholds: ThresholdDecision[] }) {
  const base = baseOption();
  const rules = thresholds.filter((t) => t.parameter === data.parameter);
  const history = data.history.slice(-48);
  const anchor = history.length ? history[history.length - 1] : null;
  const fc = anchor ? [{ target_time: anchor.timestamp, prediction: anchor.value, lower_bound: anchor.value, upper_bound: anchor.value }, ...data.points] : data.points;
  const option = {
    ...base,
    yAxis: { ...base.yAxis, name: `${data.label} (${data.unit})`, scale: true },
    legend: { ...base.legend, data: ["Observed", "Forecast", "Prediction band (95%, approx.)"] },
    tooltip: { ...base.tooltip, valueFormatter: (v: number) => (v === null || v === undefined ? "—" : fmtNum(v, 2)) },
    series: [
      { name: "Observed", type: "line", showSymbol: false, connectNulls: false, lineStyle: { width: 2, color: C.ink }, itemStyle: { color: C.ink },
        data: history.map((p) => [p.timestamp, p.value]),
        markLine: { symbol: "none", silent: true, data: [
          ...(data.based_on_until ? [{ xAxis: data.based_on_until, lineStyle: { color: C.muted, type: "dotted" }, label: { formatter: "Latest data", fontSize: 10, color: C.muted } }] : []),
          ...rules.map((r) => ({ yAxis: r.threshold, lineStyle: { color: C.alert, type: "dashed" }, label: { formatter: `Threshold ${r.threshold}`, fontSize: 10, color: C.alert, position: "insideEndTop" } })),
        ] } },
      { name: "band-low", type: "line", stack: "fc", showSymbol: false, lineStyle: { opacity: 0 }, tooltip: { show: false },
        data: fc.map((p) => [p.target_time, p.lower_bound]) },
      { name: "Prediction band (95%, approx.)", type: "line", stack: "fc", showSymbol: false, lineStyle: { opacity: 0 },
        areaStyle: { color: "rgba(15,110,116,0.16)" }, itemStyle: { color: "rgba(15,110,116,0.35)" }, tooltip: { show: false },
        data: fc.map((p) => [p.target_time, p.upper_bound !== null && p.lower_bound !== null ? (p.upper_bound as number) - (p.lower_bound as number) : null]) },
      { name: "Forecast", type: "line", symbol: "circle", symbolSize: 5, lineStyle: { width: 2, type: "dashed", color: C.teal }, itemStyle: { color: C.teal },
        data: fc.map((p) => [p.target_time, p.prediction]) },
    ],
  };
  return <EChart className="chart" option={option} />;
}
