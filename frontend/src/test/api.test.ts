import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../services/api";
import { useDashboardStore } from "../state/dashboardStore";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("builds zone URLs with query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ zone_id: "zone_a" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.trends("zone_a", "pm25", "6h");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/zones\/zone_a\/trends\?parameter=pm25&time_range=6h$/);
  });
  it("surfaces backend validation messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "bad parameter" }] }), { status: 422 })));
    await expect(api.summary("zone_a", "24h")).rejects.toMatchObject({ status: 422, message: "bad parameter" });
  });
  it("reports an unreachable backend clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await api.health().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toMatch(/Cannot reach the EnviroPulse API/);
  });
  it("sends feedback as JSON POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1 }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.feedback({ zone_id: "zone_a", feedback_type: "confirm", alert_id: 3 });
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toMatchObject({ zone_id: "zone_a", feedback_type: "confirm", alert_id: 3 });
  });
});

describe("dashboard store", () => {
  it("changing zone clears the selected anomaly and alert so panels stay in sync", () => {
    const s = useDashboardStore.getState();
    s.selectAnomaly(5); s.selectAlert(9); s.setZone("zone_b");
    const n = useDashboardStore.getState();
    expect(n.selectedZoneId).toBe("zone_b");
    expect(n.selectedAnomalyId).toBeNull();
    expect(n.selectedAlertId).toBeNull();
  });
});
