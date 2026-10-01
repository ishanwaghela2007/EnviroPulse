import { EChart } from "../../charts/EChart";
import { C, baseOption } from "../../charts/base";
import { EVENT_LABEL } from "../../format";
import type { ThresholdDecision, TrendData } from "../../types/api";

export function TrendChart({ data, thresholds }: { data: TrendData; thresholds: ThresholdDecision[] }) {
  const base = baseOption();
  const rules = thresholds.filter((t) => t.parameter === data.parameter);
  const option = {
    ...base,
    yAxis: [
      { ...base.yAxis, name: `${data.label} (${data.unit})`, scale: true },
      { ...base.yAxis, name: "Output (%)", min: 0, max: 100, splitLine: { show: false }, position: "right", nameTextStyle: { ...base.yAxis.nameTextStyle, align: "right" } },
    ],
    series: [
      {
        name: `${data.label} zone mean`, type: "line", yAxisIndex: 0, showSymbol: false, connectNulls: false,
        lineStyle: { width: 2, color: C.teal }, itemStyle: { color: C.teal }, z: 5,
        data: data.series.map((p) => [p.timestamp, p.value]),
        markLine: rules.length ? { symbol: "none", silent: true, lineStyle: { color: C.alert, type: "dashed" },
          label: { formatter: (m: { value: number }) => `Threshold ${m.value} ${data.unit}`, color: C.alert, fontSize: 11, position: "insideEndTop" },
          data: rules.map((r) => ({ yAxis: r.threshold })) } : undefined,
        markArea: {
          silent: false, itemStyle: { color: "rgba(122,63,176,0.08)" },
          label: { color: C.anomaly, fontSize: 10, position: "insideTopLeft" },
          data: data.event_markers.map((e) => [
            { xAxis: e.start_time, name: EVENT_LABEL[e.type] ?? e.type },
            { xAxis: e.end_time ?? data.window.end },
          ]),
        },
      },
      ...data.factory_series.map((f, i) => ({
        name: f.name.replace(" (fictional)", ""), type: "line", yAxisIndex: 1, showSymbol: false, connectNulls: false,
        lineStyle: { width: 1.2, type: "dashed", color: C.factory[i % 3] }, itemStyle: { color: C.factory[i % 3] },
        data: f.points.map((p) => [p.timestamp, p.value]),
      })),
    ],
  };
  return <EChart className="chart" option={option} />;
}
