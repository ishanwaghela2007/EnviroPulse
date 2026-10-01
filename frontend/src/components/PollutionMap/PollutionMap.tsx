import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Marker, Polygon, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import { EVENT_LABEL, fmtDateTime, fmtNum } from "../../format";
import { eventIcon, factoryIcon, levelColor, polygonLatLngs, sparkline } from "../../map/mapUtils";
import { useDashboardStore } from "../../state/dashboardStore";
import type { MapData, Zone } from "../../types/api";

function FitZone({ zone }: { zone: Zone | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (zone) map.fitBounds(L.latLngBounds(polygonLatLngs(zone.geometry)), { padding: [36, 36], maxZoom: 14 });
  }, [zone?.id, map]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Keeps Leaflet in sync with its (flexible) container and re-frames the selected zone after layout changes. */
function ResizeWatcher({ zone }: { zone: Zone | undefined }) {
  const map = useMap();
  useEffect(() => {
    let last = "";
    const ro = new ResizeObserver(([entry]) => {
      const size = `${Math.round(entry.contentRect.width)}x${Math.round(entry.contentRect.height)}`;
      if (size === last) return;
      last = size;
      map.invalidateSize();
      if (zone) map.fitBounds(L.latLngBounds(polygonLatLngs(zone.geometry)), { padding: [36, 36], maxZoom: 14 });
    });
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map, zone?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export function PollutionMap({ data }: { data: MapData | null }) {
  const zones = useDashboardStore((s) => s.zones);
  const selected = useDashboardStore((s) => s.selectedZoneId);
  const setZone = useDashboardStore((s) => s.setZone);
  const selectedZone = zones.find((z) => z.id === selected);
  const center: [number, number] = selectedZone ? [selectedZone.centroid.lat, selectedZone.centroid.lon] : [19.05, 73.0];
  const intensity = new Map((data?.intensity ?? []).map((i) => [i.sensor_id, i]));
  const showData = data && data.zone_id === selected;
  return (
    <div className="map-wrap">
      <MapContainer center={center} zoom={12} scrollWheelZoom preferCanvas={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                   url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitZone zone={selectedZone} />
        <ResizeWatcher zone={selectedZone} />
        {zones.map((z) => {
          const isSel = z.id === selected;
          return (
            <Polygon key={`${z.id}-${isSel}`} positions={polygonLatLngs(z.geometry)}
                     pathOptions={{ color: isSel ? "#0F6E74" : "#5B6B6F", weight: isSel ? 3 : 1.5, dashArray: isSel ? undefined : "5 5",
                                    fillColor: isSel ? "#0F6E74" : "#5B6B6F", fillOpacity: isSel ? 0.08 : 0.04 }}
                     eventHandlers={{ click: () => setZone(z.id) }}>
              <Tooltip sticky>{z.name}{z.latest_aqi !== null ? ` · AQI ${z.latest_aqi}` : ""}{z.open_alerts ? ` · ${z.open_alerts} open alert(s)` : ""}{!isSel ? " — click to select" : ""}</Tooltip>
            </Polygon>
          );
        })}
        {showData && data.sensors.map((s) => {
          const hit = intensity.get(s.id);
          return hit ? (
            <CircleMarker key={`h-${s.id}`} center={[s.lat, s.lon]} radius={16 + Math.min(hit.level, 2) * 14} interactive={false}
                          pathOptions={{ stroke: false, fillColor: levelColor(hit.level), fillOpacity: 0.28 }} />
          ) : null;
        })}
        {showData && data.sensors.map((s) => (
          <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={s.type === "air" ? 7 : 6}
                        pathOptions={{ color: "#fff", weight: 2, fillColor: s.type === "air" ? "#A86200" : "#1F6FB2", fillOpacity: 1 }}>
            <Popup>
              <div className="pop">
                <h4>{s.name}</h4>
                <div className="meta">{s.type === "air" ? "Air" : "Water"} sensor · {s.is_simulated ? <span className="badge sim">SIMULATED DEMO STREAM</span> : s.source}</div>
                <table><tbody>
                  {s.latest.map((r) => (
                    <tr key={r.parameter}>
                      <td>{r.label}</td>
                      <td className="num" style={{ textAlign: "right" }}>{r.value === null ? "missing" : `${fmtNum(r.value, r.unit === "pH" ? 2 : 1)} ${r.unit}`}</td>
                      <td><span className={`qf ${r.quality_flag}`} title={r.quality_reason ?? ""}>{r.quality_flag}</span></td>
                      <td className="muted">{fmtDateTime(r.timestamp)}</td>
                    </tr>
                  ))}
                </tbody></table>
              </div>
            </Popup>
          </CircleMarker>
        ))}
        {showData && data.factories.map((f) => (
          <Marker key={f.id} position={[f.lat, f.lon]} icon={factoryIcon(f.status)}>
            <Popup>
              <div className="pop">
                <h4>{f.name}</h4>
                <div className="meta">{f.sector} · state: <b>{f.latest_output?.operating_state ?? f.status}</b></div>
                <div>Production level <b className="num">{fmtNum(f.latest_output?.value, 1)}%</b> <span className="muted">at {fmtDateTime(f.latest_output?.timestamp)}</span></div>
                <div className="meta" style={{ marginTop: 6 }}>Output, last 24 h of data</div>
                <div dangerouslySetInnerHTML={{ __html: sparkline(f.output_trend) }} />
                <div className="meta">Simulated operations feed</div>
              </div>
            </Popup>
          </Marker>
        ))}
        {showData && data.events.map((e) => (
          <Marker key={e.id} position={[e.lat, e.lon]} icon={eventIcon(e.active_at_latest)}>
            <Popup>
              <div className="pop">
                <h4>{EVENT_LABEL[e.type] ?? e.type}</h4>
                <div className="meta">{e.severity} severity · {e.active_at_latest ? "active now" : "in selected range"}</div>
                <div>{e.description}</div>
                <div className="meta" style={{ marginTop: 6 }}>{fmtDateTime(e.start_time)} → {e.end_time ? fmtDateTime(e.end_time) : "open-ended"}</div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <div className="legend" aria-label="Map legend">
        <div className="legend-row"><span className="sw" style={{ borderRadius: "50%", background: "#A86200" }} /> Air sensor</div>
        <div className="legend-row"><span className="sw" style={{ borderRadius: "50%", background: "#1F6FB2" }} /> Water sensor</div>
        <div className="legend-row"><span className="sw" style={{ background: "#13262B", border: "2px solid #F2B544" }} /> Factory</div>
        <div className="legend-row"><span className="sw" style={{ transform: "rotate(45deg) scale(.8)", background: "#7A3FB0" }} /> Local event</div>
        <div className="legend-row"><span className="sw" style={{ borderRadius: "50%", background: "linear-gradient(90deg,#2E9E6A,#E3B53A,#C23B22)" }} /> Level vs threshold</div>
      </div>
    </div>
  );
}
