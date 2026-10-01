import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AlertCard } from "../components/AlertPanel/AlertPanel";
import { KpiRow } from "../components/KpiRow/KpiRow";
import { alertFixture, summaryFixture } from "./fixtures";

describe("KpiRow", () => {
  it("renders API values, never invented ones", () => {
    render(<KpiRow summary={summaryFixture} />);
    expect(screen.getByTestId("kpi-aqi").textContent).toContain("142");
    expect(screen.getByTestId("kpi-aqi").textContent).toContain("Moderate");
    expect(screen.getByTestId("kpi-water").textContent).toContain("Within limits");
    expect(screen.getByTestId("kpi-water").textContent).toContain("SIMULATED DEMO STREAM");
    expect(screen.getByTestId("kpi-anomalies").textContent).toContain("3");
    expect(screen.getByTestId("kpi-alerts").textContent).toContain("2");
  });
  it("shows placeholders while loading", () => {
    render(<KpiRow summary={null} />);
    expect(screen.getAllByText("—")).toHaveLength(4);
  });
  it("shows no AQI value when data is missing", () => {
    render(<KpiRow summary={{ ...summaryFixture, aqi: { ...summaryFixture.aqi, status: "NO_DATA", value: null } }} />);
    expect(screen.getByTestId("kpi-aqi").textContent).toContain("No recent air data");
  });
});

describe("AlertCard", () => {
  it("shows every required alert field", () => {
    render(<AlertCard alert={alertFixture} />);
    const text = document.body.textContent ?? "";
    for (const s of ["Industrial Zone A", "PM2.5", "86.20", "60 µg/m³", "high", "active", "3 consecutive windows",
                     "Inspect stack emissions", "estimate, not proof of cause"]) {
      expect(text).toContain(s);
    }
  });
});
