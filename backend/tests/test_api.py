"""API contract tests (FastAPI TestClient against the seeded database)."""
import json
from datetime import datetime, timedelta


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"]["status"] == "ok"
    assert body["database"]["detail"]["postgis"] and body["redis"]["status"] == "ok"
    assert body["latest_data_timestamp"] and isinstance(body["data_version"], int)


def test_source_health_is_honest(client):
    src = {s["source_name"]: s for s in client.get("/api/v1/source-health").json()["sources"]}
    assert src["sim_water"]["status"] == "SIMULATED" and src["sim_water"]["is_simulated"]
    assert "SIMULATED DEMO STREAM" in src["sim_water"]["label"]
    assert src["openaq"]["status"] == "OFFLINE" and "not configured" in src["openaq"]["error_message"]
    assert src["cpcb"]["status"] == "OFFLINE" and "reference" in src["cpcb"]["error_message"].lower()


def test_zones_endpoint(client):
    zones = client.get("/api/v1/zones").json()["zones"]
    assert [z["id"] for z in zones] == ["zone_a", "zone_b", "zone_c"]
    for z in zones:
        assert z["geometry"]["type"] == "Polygon" and "synthetic" in z["boundary_note"].lower()
        assert z["latest_aqi"] is not None


def test_summary_kpis_come_from_data(client):
    s = client.get("/api/v1/zones/zone_a/summary", params={"time_range": "24h"}).json()
    assert s["aqi"]["status"] == "OK" and 0 < s["aqi"]["value"] <= 500 and "not an official AQI" in s["aqi"]["method"]
    assert s["water"]["status"] in ("Within limits", "Outside limits", "No data") and s["water"]["is_simulated"]
    assert {p["unit"] for p in s["water"]["parameters"]} == {"pH", "NTU", "mg/L"}
    assert [p["stage"] for p in s["pipeline"]] == ["collect", "unify", "detect", "explain", "predict", "alert"]
    assert s["window"]["anchor"] == "latest_zone_data" and len(s["threshold_decisions"]) == 7


def test_trends_timestamps_units_and_context(client):
    t = client.get("/api/v1/zones/zone_b/trends", params={"parameter": "turbidity", "time_range": "7d"}).json()
    assert t["unit"] == "NTU" and t["label"] == "Turbidity"
    ts = [datetime.fromisoformat(p["timestamp"]) for p in t["series"]]
    assert all(b - a == timedelta(minutes=15) for a, b in zip(ts, ts[1:]))
    assert len(t["factory_series"]) == 2 and any(e["type"] == "industrial_activity" for e in t["event_markers"])
    assert t["source_label"] == "SIMULATED DEMO STREAM"


def test_map_layers(client):
    m = client.get("/api/v1/zones/zone_a/map", params={"parameter": "pm25"}).json()
    assert {s["type"] for s in m["sensors"]} == {"air", "water"} and len(m["factories"]) == 3
    latest = m["sensors"][0]["latest"][0]
    assert {"value", "timestamp", "parameter", "quality_flag", "unit"} <= latest.keys()
    assert m["factories"][0]["output_trend"] and "interpolation" in m["intensity_note"]


def test_anomalies_show_baseline_band(client):
    a = client.get("/api/v1/zones/zone_c/anomalies", params={"parameter": "pm10", "time_range": "7d"}).json()
    assert a["status"] == "OK" and a["anomalies"]
    top = max(a["anomalies"], key=lambda x: x["score"])
    point = next(p for p in a["series"] if p["timestamp"] == top["timestamp"])
    assert point["value"] > point["baseline_high"] > point["rolling_mean"] > point["baseline_low"]


def test_attribution_is_labelled_estimate(client):
    r = client.get("/api/v1/zones/zone_b/attribution", params={"parameter": "turbidity", "time_range": "7d"}).json()
    assert r["status"] == "OK" and r["label"] == "ESTIMATE" and "Not proof of causation" in r["disclaimer"]
    assert r["contributors"][0]["contributor_id"] == "fac_b2"  # simulator ground truth: textile discharge
    assert r["scatter"]["caption"] == "Association only — not proof of causation."
    assert r["unavailable_context"][0]["status"] == "unavailable"
    none = client.get("/api/v1/zones/zone_a/attribution", params={"parameter": "ph", "time_range": "1h"}).json()
    assert none["status"] == "NO_ANOMALY_IN_RANGE" and none["contributors"] == []


def test_no_response_claims_causation(client):
    texts = [client.get(u).text for u in ("/api/v1/zones/zone_b/attribution?parameter=turbidity&time_range=7d",
                                          "/api/v1/alerts?limit=100", "/api/v1/zones/zone_b/summary")]
    for t in texts:
        low = t.lower()
        for bad in ("caused by", "confirmed cause", "is the cause", "proven cause"):
            assert bad not in low


def test_forecast_response(client):
    f = client.get("/api/v1/zones/zone_a/forecast", params={"parameter": "pm25"}).json()
    assert f["status"] == "OK" and len(f["points"]) == 8 and f["model"]
    v = f["validation"]
    assert v["mae"] > 0 and v["rmse"] >= v["mae"] and set(v["candidates"]) == {"persistence", "seasonal_naive_24h", "ridge_lag"}
    assert all(p["lower_bound"] <= p["prediction"] <= p["upper_bound"] for p in f["points"])
    assert f["history"] and f["risk"]["level"]


def test_alerts_list_and_detail(client):
    alerts = client.get("/api/v1/alerts", params={"limit": 100}).json()["alerts"]
    assert alerts
    a = client.get(f"/api/v1/alerts/{alerts[0]['id']}").json()
    for key in ("zone_id", "zone_name", "parameter", "value", "threshold", "unit", "reason", "severity",
                "action_text", "status"):
        assert a[key] is not None
    assert a["log"][0]["event_type"] == "created"


def test_validation_errors(client):
    assert client.get("/api/v1/zones/nope/summary").status_code == 404
    assert client.get("/api/v1/zones/zone_a/trends", params={"parameter": "benzene"}).status_code == 422
    assert client.get("/api/v1/zones/zone_a/trends", params={"time_range": "5y"}).status_code == 422
    assert client.get("/api/v1/zones/zone_a/trends", params={"start": "2026-09-30T00:00:00Z"}).status_code == 422
    assert client.get("/api/v1/zones/zone_a/trends", params={"start": "2026-09-30T00:00:00Z",
                                                             "end": "2026-09-29T00:00:00Z"}).status_code == 422
    assert client.get("/api/v1/zones/DROP TABLE/summary").status_code in (404, 422)
    assert client.post("/api/v1/feedback", json={"zone_id": "zone_a", "feedback_type": "hack"}).status_code == 422
    assert client.post("/api/v1/alerts/999999/acknowledge", json={}).status_code == 404


def test_explicit_window(client):
    latest = datetime.fromisoformat(client.get("/api/v1/zones/zone_a/summary").json()["window"]["end"])
    r = client.get("/api/v1/zones/zone_a/trends", params={"start": (latest - timedelta(hours=2)).isoformat(),
                                                          "end": latest.isoformat()}).json()
    assert r["window"]["anchor"] == "explicit" and len(r["series"]) == 9


def test_openapi_documents_every_endpoint(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/zones", "/api/v1/zones/{zone_id}/summary", "/api/v1/zones/{zone_id}/map",
              "/api/v1/zones/{zone_id}/trends", "/api/v1/zones/{zone_id}/anomalies",
              "/api/v1/zones/{zone_id}/attribution", "/api/v1/zones/{zone_id}/forecast", "/api/v1/alerts",
              "/api/v1/alerts/{alert_id}/acknowledge", "/api/v1/feedback", "/api/v1/health", "/api/v1/source-health"):
        assert p in paths
    assert json.dumps(paths).count('"404"') >= 6
