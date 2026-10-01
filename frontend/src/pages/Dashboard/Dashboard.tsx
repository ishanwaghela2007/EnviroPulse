import { useState } from "react";
import { AlertLog, FeedbackHistory } from "../../components/AlertLog/AlertLog";
import { AlertPanel } from "../../components/AlertPanel/AlertPanel";
import { AnomalyChart } from "../../components/AnomalyChart/AnomalyChart";
import { AttributionChart } from "../../components/AttributionChart/AttributionChart";
import { DemoDock } from "../../components/DemoDock/DemoDock";
import { ForecastChart } from "../../components/ForecastChart/ForecastChart";
import { Header } from "../../components/Header/Header";
import { KpiRow } from "../../components/KpiRow/KpiRow";
import { Panel } from "../../components/Panel/Panel";
import { PipelineRail } from "../../components/PipelineRail/PipelineRail";
import { PollutionMap } from "../../components/PollutionMap/PollutionMap";
import { TrendChart } from "../../components/TrendChart/TrendChart";
import { ZoneDetailsDrawer } from "../../components/ZoneDetailsDrawer/ZoneDetailsDrawer";
import { fmtDateTime, fmtNum, tzLabel } from "../../format";
import { useAlerts } from "../../hooks/useAlerts";
import { useAnomalies } from "../../hooks/useAnomalies";
import { useAttribution } from "../../hooks/useAttribution";
import { useDashboard, useHealthPolling } from "../../hooks/useDashboard";
import { useForecast } from "../../hooks/useForecast";
import { useMapData } from "../../hooks/useMapData";
import { useTrends } from "../../hooks/useTrends";
import { useZones } from "../../hooks/useZones";
import { useDashboardStore } from "../../state/dashboardStore";

export function Dashboard() {
  useHealthPolling(); useZones(); useDashboard(); useMapData(); useTrends(); useAnomalies(); useAttribution(); useForecast(); useAlerts();
  const s = useDashboardStore();
  const [drawer, setDrawer] = useState(false);
  // Demo controls start collapsed on phones so they do not cover a quarter of the screen.
  const [dockOpen, setDockOpen] = useState(() => typeof window === "undefined" || !window.matchMedia("(max-width: 700px)").matches);
  const dockShown = !!s.health?.demo_controls_enabled && dockOpen;
  const thresholds = s.dashboardSummary?.threshold_decisions ?? [];
  const sameParam = <T extends { parameter: string }>(d: T | null) => (d && d.parameter === s.selectedParameter ? d : null);
  const trend = sameParam(s.trendData), anomalies = sameParam(s.anomalyData), forecast = sameParam(s.forecastData);
  const att = s.attributionData;

  return (
    <>
      <Header />
      <PipelineRail />
      <main className={`page ${dockShown ? "with-dock" : ""}`}>
        {s.errors.global && <div className="banner" role="alert">{s.errors.global} Showing the last data received.</div>}
        {s.health && s.health.status !== "ok" && !s.errors.global && (
          <div className="banner info">Backend running in degraded mode (database {s.health.database.status}, cache {s.health.redis.status}).</div>
        )}
        <KpiRow summary={s.dashboardSummary} />

        <div className="hero">
          <Panel id="map" title="Pollution map" question="Where is it happening?" className="map-panel"
                 loading={s.loading.map} error={s.errors.map}
                 right={<button className="btn" onClick={() => setDrawer(true)}>Zone details</button>}
                 foot={<>{s.mapData?.intensity_note} Times shown in {tzLabel}. Synthetic zone boundaries.</>}>
            <PollutionMap data={s.mapData} />
          </Panel>
          <Panel id="alerts" title="Current alert" question="What should the officer do?" loading={s.loading.alerts} error={s.errors.alerts}>
            <AlertPanel />
          </Panel>
        </div>

        <div className="charts">
          <Panel id="trend" title="Trend" question="When did it change?" loading={s.loading.trends} error={s.errors.trends}
                 right={trend && <span className="badge sim">{trend.source_label}</span>}
                 empty={trend && trend.series.every((p) => p.value === null) ? { title: "No data in this range", body: "No valid readings were aligned for this zone and parameter." } : null}
                 foot={trend && <>Zone mean of valid sensors per {trend.window.window_minutes}-min window. {trend.missing_windows} missing window{trend.missing_windows === 1 ? "" : "s"} shown as gaps (never filled). Dashed lines: factory output, right axis. Shaded: local events.</>}>
            {trend && <TrendChart data={trend} thresholds={thresholds} />}
          </Panel>

          <Panel id="anomaly" title="Anomaly timeline" question="Is this unusual?" loading={s.loading.anomalies} error={s.errors.anomalies}
                 empty={anomalies && anomalies.status !== "OK" ? { title: anomalies.status === "NO_DATA" ? "No data in this range" : "Insufficient history",
                   body: anomalies.status === "NO_DATA" ? "Nothing to analyse for this zone and parameter." : `A baseline needs at least ${anomalies.detector.baseline_windows} windows of history; no anomaly is reported until then.` } : null}
                 foot={anomalies && <>{anomalies.anomalies.length} anomal{anomalies.anomalies.length === 1 ? "y" : "ies"} in range. {anomalies.note} Click a violet point to explain it.</>}>
            {anomalies && <AnomalyChart data={anomalies} selectedId={s.selectedAnomalyId} onSelect={s.selectAnomaly} />}
          </Panel>

          <Panel id="attribution" title="Source attribution" question="What is the likely contributor?" loading={s.loading.attribution} error={s.errors.attribution}
                 right={<span className="badge estimate">ESTIMATE</span>}
                 empty={att && att.status !== "OK" ? { title: "Nothing to explain", body: att.message ?? "No anomaly in the selected range." } : null}
                 foot={att && att.status === "OK" && <>{att.disclaimer} Explaining the {att.anomaly && `${fmtNum(att.anomaly.value, 1)} ${s.anomalyData?.unit ?? ""} anomaly at ${fmtDateTime(att.anomaly.timestamp)}`}. {att.unavailable_context.map((u) => u.reason).join(" ")}</>}>
            {att && att.status === "OK" && <AttributionChart data={att} />}
          </Panel>

          <Panel id="forecast" title="Forecast" question="What might happen next?" loading={s.loading.forecast} error={s.errors.forecast}
                 empty={forecast && forecast.status !== "OK" ? { title: forecast.status === "MODEL_ERROR" ? "Forecast unavailable" : "Insufficient history for forecast", body: forecast.message ?? "" } : null}
                 foot={forecast && forecast.status === "OK" && forecast.validation && (
                   <div style={{ display: "grid", gap: 6 }}>
                     {forecast.risk && <div className={`risk ${forecast.risk.level}`}>{forecast.risk.message}</div>}
                     <div className="metrics num">
                       <span>Model <b>{forecast.model}</b></span>
                       <span>MAE <b>{fmtNum(forecast.validation.mae, 2)}</b></span>
                       <span>RMSE <b>{fmtNum(forecast.validation.rmse, 2)}</b> {forecast.unit}</span>
                       <span>Next {forecast.horizon_windows} windows · validated on {forecast.validation.holdout_windows} held-out windows</span>
                     </div>
                     <span>{forecast.validation.band}</span>
                   </div>)}>
            {forecast && forecast.status === "OK" && <ForecastChart data={forecast} thresholds={thresholds} />}
          </Panel>
        </div>

        <div className="bottom">
          <Panel id="alert-log" title="Alert log" question="What happened, and what was done?" loading={s.loading.alerts}>
            <AlertLog />
          </Panel>
          <Panel id="feedback" title="Operator feedback" question="Stored for future recalibration" loading={s.loading.feedback} error={s.errors.feedback}>
            <FeedbackHistory />
          </Panel>
        </div>
      </main>
      <ZoneDetailsDrawer open={drawer} onClose={() => setDrawer(false)} />
      <DemoDock open={dockOpen} onToggle={() => setDockOpen((o) => !o)} />
    </>
  );
}
