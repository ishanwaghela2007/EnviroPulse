"""Documented index formulas and validation metrics."""
import math

import numpy as np

# CPCB National AQI (NAQI) breakpoints: (conc_lo, conc_hi, index_lo, index_hi)
NAQI_BREAKPOINTS = {
    "pm25": [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200), (91, 120, 201, 300), (121, 250, 301, 400),
             (251, 500, 401, 500)],
    "pm10": [(0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200), (251, 350, 201, 300), (351, 430, 301, 400),
             (431, 600, 401, 500)],
    "no2": [(0, 40, 0, 50), (41, 80, 51, 100), (81, 180, 101, 200), (181, 280, 201, 300), (281, 400, 301, 400),
            (401, 800, 401, 500)],
}
NAQI_CATEGORIES = [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very poor"),
                   (500, "Severe")]
AQI_METHOD = ("Indicative AQI: CPCB NAQI sub-index breakpoints applied to 1-hour zone means of PM2.5, PM10 and NO₂. "
              "Official NAQI uses 24-hour averages, so this is not an official AQI.")


def naqi_subindex(param: str, conc: float | None) -> float | None:
    if conc is None or (isinstance(conc, float) and math.isnan(conc)) or param not in NAQI_BREAKPOINTS:
        return None
    c = max(0.0, float(round(conc)))
    for lo, hi, ilo, ihi in NAQI_BREAKPOINTS[param]:
        if c <= hi:
            c_eff = max(c, lo)
            return ilo + (ihi - ilo) * (c_eff - lo) / (hi - lo)
    return 500.0


def naqi_category(aqi: float | None) -> str | None:
    if aqi is None:
        return None
    for upper, name in NAQI_CATEGORIES:
        if aqi <= upper:
            return name
    return "Severe"


def indicative_aqi(concs: dict[str, float | None]) -> tuple[int | None, str | None, str | None]:
    subs = {p: naqi_subindex(p, v) for p, v in concs.items()}
    subs = {p: s for p, s in subs.items() if s is not None}
    if not any(p in subs for p in ("pm25", "pm10")):
        return None, None, None  # NAQI requires at least one particulate pollutant
    dominant = max(subs, key=subs.get)
    aqi = int(round(subs[dominant]))
    return aqi, naqi_category(aqi), dominant


def mae(y, yhat) -> float:
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))


def rmse(y, yhat) -> float:
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(yhat, float)) ** 2)))
