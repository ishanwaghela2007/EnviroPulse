"""Deterministic generative model for the SIMULATED DEMO STREAM.

Every value is a function of (seed, sensor/factory, window time) plus explicit scenario overrides, so the
seed and the golden demo are exactly repeatable. Output records use the same raw format a real
connector delivers and pass through the normal ingestion/validation pipeline."""
import math
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from app.core.parameters import PARAMETERS
from app.simulation import world

SIM_AIR, SIM_WATER, SIM_FACTORY, SIM_EVENTS = "sim_air", "sim_water", "sim_factory", "sim_events"
IST = timezone(timedelta(hours=5, minutes=30))


def _rng(*parts: int) -> np.random.Generator:
    return np.random.default_rng([abs(int(p)) for p in parts])


def _h(obj) -> int:
    """Stable hash (the builtin hash of str is randomized per process)."""
    return zlib.crc32(repr(obj).encode())


def _epoch_min(ts: datetime) -> int:
    return int(ts.timestamp() // 60)


@dataclass
class Overrides:
    """Scenario overrides for one window."""
    factory_levels: dict[str, float] = field(default_factory=dict)            # factory_id -> level %
    point_spikes: dict[tuple[str, str], float] = field(default_factory=dict)  # (zone, param) -> added value


class WorldModel:
    def __init__(self, seed: int):
        self.seed = seed
        self.factories = {f["id"]: f for f in world.FACTORIES}

    def factory_level(self, fid: str, ts: datetime, overrides: dict[datetime, Overrides]) -> float:
        o = overrides.get(ts)
        if o and fid in o.factory_levels:
            return o.factory_levels[fid]
        f = self.factories[fid]
        local = ts.astimezone(IST)
        hour = local.hour + local.minute / 60
        shift = 7.0 * math.sin(2 * math.pi * (hour - 9) / 24)  # day shift runs higher
        noise = _rng(self.seed, 101, _h(fid) % 10_000, _epoch_min(ts)).normal(0, 3.0)
        return float(np.clip(f["nominal"] + shift + noise, 0, 100))

    def zone_value(self, zone: str, param: str, ts: datetime, overrides: dict[datetime, Overrides],
                   events_active: set[str]) -> float:
        base, amp, _ = world.ZONE_BASELINES[zone][param]
        local = ts.astimezone(IST)
        hour = local.hour + local.minute / 60
        if PARAMETERS[param].domain == "air":  # morning + evening peaks
            diurnal = amp * (0.6 * math.cos(2 * math.pi * (hour - 9) / 24) + 0.4 * math.cos(4 * math.pi * (hour - 20) / 24))
        else:
            diurnal = amp * math.sin(2 * math.pi * (hour - 14) / 24)
        value = base + diurnal
        step = timedelta(minutes=15)
        for f in world.FACTORIES:
            if f["zone"] != zone or param not in f["effects"]:
                continue
            k, lag = f["effects"][param]
            value += k * (self.factory_level(f["id"], ts - lag * step, overrides) - f["nominal"])
        for etype in events_active:
            value += world.EVENT_EFFECTS.get(etype, {}).get(param, 0.0)
        if param == "dissolved_oxygen":  # DO falls when turbidity load rises
            t_base = world.ZONE_BASELINES[zone]["turbidity"][0]
            turb = self.zone_value(zone, "turbidity", ts, overrides, events_active)
            value -= 0.06 * max(0.0, turb - t_base)
        o = overrides.get(ts)
        if o and (zone, param) in o.point_spikes:
            value += o.point_spikes[(zone, param)]
        return value

    def sensor_readings(self, ts: datetime, overrides: dict[datetime, Overrides],
                        events_by_zone: dict[str, set[str]]) -> list[dict]:
        out = []
        for sid, zone, stype, _name, _lat, _lon, mult in world.SENSORS:
            params = world.AIR if stype == "air" else world.WATER
            source = SIM_AIR if stype == "air" else SIM_WATER
            obs_ts = ts + timedelta(minutes=2, seconds=(_h(sid) % 50))
            for p in params:
                rng = _rng(self.seed, 202, _h((sid, p)) % 100_000, _epoch_min(ts))
                sd = world.ZONE_BASELINES[zone][p][2]
                v = self.zone_value(zone, p, ts, overrides, events_by_zone.get(zone, set())) * mult + rng.normal(0, sd)
                value: float | None = round(max(v, 0.0), 3 if p == "ph" else 2)
                u = rng.random()  # realistic data-quality issues on one sensor (deterministic)
                if sid == "c_air_2" and u < 0.015:
                    value = None                      # dropped packet -> MISSING
                elif sid == "c_air_2" and p == "pm25" and u > 0.997:
                    value = 900.0                     # glitch -> SUSPICIOUS (outside plausible range)
                out.append({"source": source, "sensor_id": sid, "timestamp": obs_ts.isoformat(), "parameter": p,
                            "value": value, "unit": PARAMETERS[p].unit,
                            "source_record_id": f"{sid}:{p}:{obs_ts.strftime('%Y%m%dT%H%M%S')}"})
        return out

    def factory_records(self, ts: datetime, overrides: dict[datetime, Overrides]) -> list[dict]:
        rows = []
        for f in world.FACTORIES:
            lvl = round(self.factory_level(f["id"], ts, overrides), 2)
            rows.append({"source": SIM_FACTORY, "factory_id": f["id"], "timestamp": ts.isoformat(),
                         "metric": "production_level", "value": lvl, "unit": "%",
                         "operating_state": "operating" if lvl > 5 else "idle"})
        return rows
