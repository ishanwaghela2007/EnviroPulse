// Tree-shaken ECharts: only the chart types and components the dashboard uses are bundled.
import ReactEChartsCore from "echarts-for-react/lib/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { CSSProperties } from "react";

echarts.use([LineChart, BarChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent,
  MarkAreaComponent, CanvasRenderer]);

interface Props { option: object; className?: string; style?: CSSProperties; onEvents?: Record<string, Function> }

export function EChart({ option, className, style, onEvents }: Props) {
  return <ReactEChartsCore echarts={echarts} option={option} className={className} style={style} notMerge onEvents={onEvents} />;
}
