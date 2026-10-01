"""OpenAQ v3 connector (public air-quality measurements). Requires OPENAQ_API_KEY (sent as X-API-Key).

Flow: for each zone centroid -> GET /locations?coordinates=lat,lon&radius=R -> GET /locations/{id}/latest.
Each latest value becomes a raw observation with station coordinates; ingestion assigns it to a zone via
PostGIS and quarantines stations outside all configured zones.
Not tested against the live API in the build environment (network allow-list); covered by mocked tests.
OpenAQ aggregates data from many providers: values are not necessarily government-operated or real-time."""
import time

import httpx

from app.connectors.base import ConnectorBatch, ConnectorError, ConnectorNotConfigured, SourceInfo
from app.core.config import get_settings
from app.core.parameters import OPENAQ_PARAMETER_MAP

INFO = SourceInfo("openaq", "OpenAQ public air-quality API", "air", False, "observations")


def fetch(zone_centroids: list[tuple[float, float]], client: httpx.Client | None = None) -> ConnectorBatch:
    s = get_settings()
    if not s.openaq_api_key:
        raise ConnectorNotConfigured("OPENAQ_API_KEY is not configured; no OpenAQ data is fetched.")
    own = client is None
    client = client or httpx.Client(timeout=s.http_timeout_seconds)
    headers = {"X-API-Key": s.openaq_api_key, "Accept": "application/json"}
    t0 = time.perf_counter()
    records: list[dict] = []
    try:
        for lat, lon in zone_centroids:
            r = client.get(f"{s.openaq_base_url}/locations", headers=headers,
                           params={"coordinates": f"{lat:.5f},{lon:.5f}", "radius": s.openaq_search_radius_m,
                                   "limit": 100})
            r.raise_for_status()
            for loc in r.json().get("results", []):
                sensor_param = {}
                for sensor in loc.get("sensors", []):
                    pname = (sensor.get("parameter") or {}).get("name")
                    if pname in OPENAQ_PARAMETER_MAP:
                        sensor_param[sensor["id"]] = (OPENAQ_PARAMETER_MAP[pname],
                                                      (sensor.get("parameter") or {}).get("units"))
                if not sensor_param:
                    continue
                lr = client.get(f"{s.openaq_base_url}/locations/{loc['id']}/latest", headers=headers)
                lr.raise_for_status()
                for m in lr.json().get("results", []):
                    sid = m.get("sensorsId")
                    if sid not in sensor_param:
                        continue
                    param, unit = sensor_param[sid]
                    coords = m.get("coordinates") or loc.get("coordinates") or {}
                    ts = (m.get("datetime") or {}).get("utc")
                    records.append({"source": "openaq", "sensor_id": f"openaq:{sid}",
                                    "sensor_name": loc.get("name"), "latitude": coords.get("latitude"),
                                    "longitude": coords.get("longitude"), "timestamp": ts, "parameter": param,
                                    "value": m.get("value"), "unit": unit,
                                    "source_record_id": f"openaq:{sid}:{ts}"})
    except httpx.HTTPError as exc:
        raise ConnectorError(f"OpenAQ request failed: {type(exc).__name__}") from exc
    finally:
        if own:
            client.close()
    return ConnectorBatch(records, (time.perf_counter() - t0) * 1000)
