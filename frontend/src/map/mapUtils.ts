import L from "leaflet";

export const polygonLatLngs = (g: GeoJSON.Polygon): [number, number][] =>
  g.coordinates[0].map(([lon, lat]) => [lat, lon] as [number, number]);

/** Colour for a value relative to its configured threshold (level = value / threshold, from the API). */
export function levelColor(level: number): string {
  if (level >= 1) return "#C23B22";
  if (level >= 0.8) return "#E0822B";
  if (level >= 0.6) return "#E3B53A";
  return "#2E9E6A";
}

export const factoryIcon = (status: string) => L.divIcon({
  className: "",
  html: `<div style="width:22px;height:22px;border-radius:4px;background:#13262B;border:2px solid ${status === "operating" ? "#F2B544" : "#9AA9AC"};display:grid;place-items:center">
    <svg width="12" height="12" viewBox="0 0 12 12"><path d="M1 11V5l3 2V5l3 2V2h3v9z" fill="${status === "operating" ? "#F2B544" : "#9AA9AC"}"/></svg></div>`,
  iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -10],
});

export const eventIcon = (active: boolean) => L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;transform:rotate(45deg);background:${active ? "#7A3FB0" : "#fff"};border:2px solid #7A3FB0;box-shadow:0 0 0 ${active ? 4 : 0}px rgba(122,63,176,.25)"></div>`,
  iconSize: [16, 16], iconAnchor: [8, 8], popupAnchor: [0, -10],
});

export function sparkline(points: { value: number | null }[], w = 200, h = 40): string {
  const vals = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  let d = "", pen = false;
  points.forEach((p, i) => {
    if (p.value === null) { pen = false; return; }
    const x = (i / (points.length - 1)) * w, y = h - ((p.value - min) / span) * (h - 4) - 2;
    d += `${pen ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)} `; pen = true;
  });
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><path d="${d}" fill="none" stroke="#A86200" stroke-width="1.6"/></svg>`;
}
