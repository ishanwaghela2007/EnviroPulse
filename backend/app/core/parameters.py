"""Parameter registry: the single source of truth for names, units and valid ranges.
The API always returns units from here, so the frontend never infers them."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    unit: str
    domain: str                       # "air" | "water"
    physical_range: tuple[float, float]   # outside -> quarantined (impossible value)
    plausible_range: tuple[float, float]  # outside -> flagged SUSPICIOUS


PARAMETERS: dict[str, ParameterSpec] = {
    "pm25": ParameterSpec("pm25", "PM2.5", "µg/m³", "air", (0, 1500), (0, 500)),
    "pm10": ParameterSpec("pm10", "PM10", "µg/m³", "air", (0, 3000), (0, 800)),
    "no2": ParameterSpec("no2", "NO₂", "µg/m³", "air", (0, 2000), (0, 400)),
    "ph": ParameterSpec("ph", "pH", "pH", "water", (0, 14), (4, 11)),
    "turbidity": ParameterSpec("turbidity", "Turbidity", "NTU", "water", (0, 4000), (0, 1000)),
    "dissolved_oxygen": ParameterSpec("dissolved_oxygen", "Dissolved oxygen", "mg/L", "water", (0, 25), (0, 16)),
}
AIR_PARAMETERS = [k for k, v in PARAMETERS.items() if v.domain == "air"]
WATER_PARAMETERS = [k for k, v in PARAMETERS.items() if v.domain == "water"]

# OpenAQ parameter names -> internal keys
OPENAQ_PARAMETER_MAP = {"pm25": "pm25", "pm10": "pm10", "no2": "no2"}

FACTORY_METRICS = {"production_level": "%"}
EVENT_TYPES = ["industrial_activity", "construction", "traffic_event", "local_event"]


def spec(key: str) -> ParameterSpec:
    if key not in PARAMETERS:
        raise KeyError(key)
    return PARAMETERS[key]
