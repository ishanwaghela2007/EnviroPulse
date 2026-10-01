"""END-TO-END: reset -> golden scenario through the real API.
new observation -> ingestion -> validation -> alignment -> analytics -> alert -> API (what the dashboard reads)
-> acknowledgement + feedback persisted. Then source outage + recovery. Runs last (mutates the database)."""
from datetime import datetime

import pytest
from sqlalchemy import text

from app.core.database import session_scope


@pytest.fixture(scope="module")
def fresh(client):
    r = client.post("/api/v1/demo/reset")
    assert r.status_code == 200
    return r.json()["seed"]


def tick(client):
    r = client.post("/api/v1/demo/tick")
    assert r.status_code == 200, r.text
    return r.json()


def pm25_alerts(client):
    return [a for a in client.get("/api/v1/alerts", params={"zone_id": "zone_a", "limit": 100}).json()["alerts"]
            if a["parameter"] == "pm25"]


def test_golden_scenario_end_to_end(client, fresh):
    v0 = client.get("/api/v1/health").json()["data_version"]
    for _ in range(4):
        t = tick(client)
    assert t["tick"] == 4 and not pm25_alerts(client)

    # tick 5: new readings -> stored -> aligned -> anomaly
    t5 = tick(client)
    window = t5["window"]
    with session_scope() as db:
        n = db.execute(text("SELECT count(*) FROM readings WHERE zone_id='zone_a' AND parameter='pm25' "
                            "AND date_bin('15 minutes', timestamp, TIMESTAMPTZ '2000-01-01') = :w"), {"w": window}).scalar()
        mean = db.execute(text("SELECT avg(value) FROM readings WHERE zone_id='zone_a' AND parameter='pm25' "
                               "AND quality_flag='VALID' AND date_bin('15 minutes', timestamp, TIMESTAMPTZ '2000-01-01') = :w"),
                          {"w": window}).scalar()
    assert n == 2  # both zone A air sensors ingested for the new window
    trend = client.get("/api/v1/zones/zone_a/trends", params={"parameter": "pm25", "time_range": "1h"}).json()
    assert trend["series"][-1]["timestamp"].startswith(window[:16]) and trend["series"][-1]["value"] == pytest.approx(mean)
    anomalies = client.get("/api/v1/zones/zone_a/anomalies", params={"parameter": "pm25", "time_range": "1h"}).json()
    assert anomalies["anomalies"] and anomalies["anomalies"][0]["timestamp"].startswith(window[:16])
    assert mean > 60 and not pm25_alerts(client)  # breach #1: persistence not met, no alert yet

    attribution = client.get("/api/v1/zones/zone_a/attribution", params={"parameter": "pm25", "time_range": "1h"}).json()
    assert attribution["label"] == "ESTIMATE"
    assert attribution["contributors"][0]["contributor_id"] == "fac_a1"  # recovers the injected ground truth
    assert attribution["contributors"][0]["best_lag_windows"] == 1

    tick(client)  # tick 6: breach #2
    summary = client.get("/api/v1/zones/zone_a/summary").json()
    pm = next(d for d in summary["threshold_decisions"] if d["parameter"] == "pm25")
    assert pm["decision"] == "pending_persistence" and pm["consecutive_breach_windows"] == 2
    assert not pm25_alerts(client)

    tick(client)  # tick 7: breach #3 -> alert
    alerts = pm25_alerts(client)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["status"] == "active" and a["zone_id"] == "zone_a" and a["value"] > a["threshold"] == 60
    assert "3 consecutive" in a["reason"] and "Likely contributors (estimate" in a["source_context"]
    fc = client.get("/api/v1/zones/zone_a/forecast", params={"parameter": "pm25"}).json()
    assert fc["status"] == "OK" and fc["based_on_until"] == a["last_breach_at"]
    s = client.get("/api/v1/zones/zone_a/summary").json()
    assert s["active_alerts"] >= 1 and s["active_anomalies"] >= 1

    for _ in range(3):  # ticks 8-10: same episode updated, never duplicated
        tick(client)
    alerts = pm25_alerts(client)
    assert len(alerts) == 1 and alerts[0]["id"] == a["id"] and alerts[0]["breach_windows"] >= 5

    ack = client.post(f"/api/v1/alerts/{a['id']}/acknowledge", json={"operator": "judge", "note": "Inspecting stack"})
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    assert client.post(f"/api/v1/alerts/{a['id']}/acknowledge", json={}).status_code == 409
    fb = client.post("/api/v1/feedback", json={"zone_id": "zone_a", "alert_id": a["id"], "feedback_type": "tag_factory",
                                               "contributor_id": "fac_a1", "feedback_text": "Confirmed on site",
                                               "operator": "judge"})
    assert fb.status_code == 201
    listed = client.get("/api/v1/feedback", params={"alert_id": a["id"]}).json()["feedback"]
    assert {f["feedback_type"] for f in listed} == {"tag_factory", "note"}

    tick(client)
    tick(client)  # ticks 11-12: two normal windows -> episode resolved
    final = client.get(f"/api/v1/alerts/{a['id']}").json()
    assert final["status"] == "resolved" and not final["episode_open"]
    log = [e["event_type"] for e in final["log"]]
    assert log[:2] == ["created", "notification_dispatched"] and "acknowledged" in log and log[-1] == "resolved"
    assert client.get("/api/v1/health").json()["data_version"] > v0


def test_source_outage_degrades_and_recovers(client, fresh):
    assert client.post("/api/v1/demo/source-outage", json={"source": "sim_air", "enabled": True}).status_code == 200
    t = tick(client)
    assert t["sources"]["sim_air"]["status"] == "failed" and t["sources"]["sim_air"]["last_known_good"]
    src = {s["source_name"]: s for s in client.get("/api/v1/source-health").json()["sources"]}
    assert src["sim_air"]["status"] == "DEGRADED" and "outage" in src["sim_air"]["error_message"]
    assert src["sim_water"]["status"] == "SIMULATED"  # other sources unaffected
    summary = client.get("/api/v1/zones/zone_a/summary").json()
    assert summary["pipeline"][0]["status"] == "degraded"
    trend = client.get("/api/v1/zones/zone_a/trends", params={"parameter": "pm25", "time_range": "1h"}).json()
    assert trend["series"][-1]["value"] is None or trend["series"][-1]["timestamp"] != t["window"]  # gap, never zero
    tick(client)
    tick(client)
    src = {s["source_name"]: s for s in client.get("/api/v1/source-health").json()["sources"]}
    assert src["sim_air"]["status"] == "OFFLINE" and src["sim_air"]["consecutive_failures"] == 3
    client.post("/api/v1/demo/source-outage", json={"source": "sim_air", "enabled": False})
    tick(client)
    src = {s["source_name"]: s for s in client.get("/api/v1/source-health").json()["sources"]}
    assert src["sim_air"]["status"] == "SIMULATED" and src["sim_air"]["consecutive_failures"] == 0


def test_concurrent_ticks_are_serialised(client, fresh):
    """Two tabs / Play + click / scheduler overlap: every concurrent tick must process a distinct window."""
    from concurrent.futures import ThreadPoolExecutor

    from app.services import demo_stream

    def one_tick(_):
        with session_scope() as db:
            return demo_stream.tick(db)["window"]

    before = client.get("/api/v1/demo/status").json()["tick"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        windows = list(pool.map(one_tick, range(4)))
    assert len(set(windows)) == 4  # no window processed twice
    assert client.get("/api/v1/demo/status").json()["tick"] == before + 4  # no tick lost
