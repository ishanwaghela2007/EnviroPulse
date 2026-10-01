"""India Open Government Data (data.gov.in) real-time air-quality resource. Requires OGD_API_KEY.

Records are station-level pollutant values with a `last_update` time (IST). Only PM2.5, PM10 and NO2 are
mapped. Field names differ between dataset versions (avg_value / pollutant_avg), both are accepted.
Before enabling in production, verify the field semantics and units against the live resource.
Not tested against the live API in the build environment (network allow-list); covered by mocked tests."""
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.connectors.base import ConnectorBatch, ConnectorError, ConnectorNotConfigured, SourceInfo
from app.core.config import get_settings

INFO = SourceInfo("ogd_aqi", "India OGD real-time air-quality resource", "air", False, "observations")
IST = timezone(timedelta(hours=5, minutes=30))
POLLUTANT_MAP = {"PM2.5": "pm25", "PM10": "pm10", "NO2": "no2"}


def fetch(state: str = "Maharashtra", client: httpx.Client | None = None) -> ConnectorBatch:
    s = get_settings()
    if not s.ogd_api_key:
        raise ConnectorNotConfigured("OGD_API_KEY is not configured; no OGD data is fetched.")
    own = client is None
    client = client or httpx.Client(timeout=s.http_timeout_seconds)
    t0 = time.perf_counter()
    try:
        r = client.get(s.ogd_aqi_base_url, params={"api-key": s.ogd_api_key, "format": "json", "limit": 1000,
                                                    "filters[state]": state})
        r.raise_for_status()
        payload = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ConnectorError(f"OGD request failed: {type(exc).__name__}") from exc
    finally:
        if own:
            client.close()
    records = []
    for rec in payload.get("records", []):
        param = POLLUTANT_MAP.get(str(rec.get("pollutant_id", "")).upper().replace("PM2.5", "PM2.5"))
        if not param:
            continue
        try:
            ts = datetime.strptime(rec["last_update"], "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST).isoformat()
        except (KeyError, ValueError):
            ts = rec.get("last_update")  # validation will quarantine an unparseable timestamp
        value = rec.get("avg_value", rec.get("pollutant_avg"))
        if value in ("NA", "na"):
            value = None
        station = rec.get("station", "unknown")
        records.append({"source": "ogd_aqi", "sensor_id": f"ogd:{station}", "sensor_name": station,
                        "latitude": rec.get("latitude"), "longitude": rec.get("longitude"), "timestamp": ts,
                        "parameter": param, "value": value, "unit": "µg/m³",
                        "source_record_id": f"ogd:{station}:{param}:{ts}"})
    return ConnectorBatch(records, (time.perf_counter() - t0) * 1000)
