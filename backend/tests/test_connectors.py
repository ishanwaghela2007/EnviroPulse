"""External connectors with mocked HTTP (the live APIs are not reachable from the build environment).
Verifies request auth, response mapping, unit handling and honest not-configured / failure behaviour."""
import httpx
import pytest

from app.connectors import cpcb, ogd_aqi, openaq
from app.connectors.base import ConnectorError, ConnectorNotConfigured
from app.core.config import get_settings


@pytest.fixture
def keys():
    s = get_settings()
    old = (s.openaq_api_key, s.ogd_api_key)
    s.openaq_api_key, s.ogd_api_key = "test-key", "test-key"
    yield
    s.openaq_api_key, s.ogd_api_key = old


def test_not_configured_sources_never_fabricate():
    with pytest.raises(ConnectorNotConfigured):
        openaq.fetch([(19.1, 73.0)])
    with pytest.raises(ConnectorNotConfigured):
        ogd_aqi.fetch()
    with pytest.raises(ConnectorNotConfigured):
        cpcb.fetch()


def test_openaq_maps_latest_measurements(keys):
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        assert req.headers["X-API-Key"] == "test-key"
        if req.url.path.endswith("/locations"):
            return httpx.Response(200, json={"results": [{"id": 7, "name": "Station X", "coordinates": {
                "latitude": 19.11, "longitude": 73.02}, "sensors": [
                {"id": 70, "parameter": {"name": "pm25", "units": "µg/m³"}},
                {"id": 71, "parameter": {"name": "o3", "units": "ppm"}}]}]})
        return httpx.Response(200, json={"results": [
            {"sensorsId": 70, "value": 44.2, "datetime": {"utc": "2026-09-30T06:00:00Z"},
             "coordinates": {"latitude": 19.11, "longitude": 73.02}},
            {"sensorsId": 71, "value": 0.03, "datetime": {"utc": "2026-09-30T06:00:00Z"}}]})

    batch = openaq.fetch([(19.1, 73.0)], client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(batch.records) == 1  # unsupported parameter (o3) not mapped
    r = batch.records[0]
    assert r["parameter"] == "pm25" and r["value"] == 44.2 and r["sensor_id"] == "openaq:70" and r["latitude"] == 19.11
    assert "test-key" not in str(seen[0].url)  # key travels in a header, never in the URL


def test_openaq_http_failure_raises_connector_error(keys):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503)))
    with pytest.raises(ConnectorError):
        openaq.fetch([(19.1, 73.0)], client=client)


def test_ogd_maps_records_and_parses_ist(keys):
    payload = {"records": [
        {"station": "Mahape, Navi Mumbai", "pollutant_id": "PM2.5", "avg_value": "48", "last_update": "30-09-2026 11:00:00",
         "latitude": "19.11", "longitude": "73.02"},
        {"station": "Mahape, Navi Mumbai", "pollutant_id": "SO2", "avg_value": "9", "last_update": "30-09-2026 11:00:00",
         "latitude": "19.11", "longitude": "73.02"},
        {"station": "Mahape, Navi Mumbai", "pollutant_id": "NO2", "avg_value": "NA", "last_update": "30-09-2026 11:00:00",
         "latitude": "19.11", "longitude": "73.02"}]}
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))
    recs = ogd_aqi.fetch(client=client).records
    assert [r["parameter"] for r in recs] == ["pm25", "no2"]
    assert recs[0]["timestamp"] == "2026-09-30T11:00:00+05:30" and recs[1]["value"] is None  # NA -> missing, not 0
