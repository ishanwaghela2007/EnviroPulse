// Shared ECharts styling. Charts render in the viewer's local time zone.
export const C = { ink: "#13262B", muted: "#6A7C80", line: "#D3DDDB", teal: "#0F6E74", air: "#A86200", water: "#1F6FB2",
  anomaly: "#7A3FB0", alert: "#C23B22", ok: "#2E7D4F", factory: ["#8C6D1F", "#5E7F86", "#B0915E"] };
export const FONT = '"Public Sans", system-ui, sans-serif';

export const baseOption = () => ({
  animation: false,
  textStyle: { fontFamily: FONT, color: C.ink },
  grid: { left: 52, right: 56, top: 58, bottom: 40 },
  tooltip: { trigger: "axis", backgroundColor: "#fff", borderColor: C.line, textStyle: { color: C.ink, fontSize: 12 } },
  legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11, color: C.muted } },
  xAxis: { type: "time", axisLine: { lineStyle: { color: C.line } }, axisLabel: { color: C.muted, fontSize: 11, hideOverlap: true },
           splitLine: { show: false } },
  yAxis: { type: "value", axisLabel: { color: C.muted, fontSize: 11 }, splitLine: { lineStyle: { color: "#EDF2F1" } },
           nameTextStyle: { color: C.muted, fontSize: 11, align: "left" } },
});
