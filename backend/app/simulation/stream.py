"""SIMULATED DEMO STREAM: turns the world model + scenario overrides into raw connector records.

History scenario (seeded):  zone B effluent/turbidity episode (anomaly + persistent breach -> alert),
                            zone A short excursion (anomaly, no alert), zone C one-window PM10 spike
                            (anomaly + transient breach, NO alert because persistence = 3).
Golden scenario (live demo, Industrial Zone A), relative to the first window after history:
  tick 1-3  normal readings
  tick 4    Apex Organics production rises (88%)
  tick 5    PM2.5 rises (1-window lag) -> anomaly; threshold breach #1 (no alert yet, persistence 3)
  tick 6    construction event starts nearby; breach #2
  tick 7    breach #3 -> ALERT created
  tick 8-10 alert updated in place (same episode, no duplicates)
  tick 10   production back to nominal; tick 11-12 PM2.5 within limits for 2 windows -> episode resolved"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.simulation import world
from app.simulation.model import SIM_EVENTS, Overrides, WorldModel

STEP = timedelta(minutes=15)
GOLDEN_FACTORY_LEVELS = {3: 88.0, 4: 96.0, 5: 97.0, 6: 96.0, 7: 95.0, 8: 90.0}   # tick index k (0-based)
GOLDEN_EVENT = {"k_start": 5, "duration_windows": 6, "type": "construction", "lat": 19.104, "lon": 73.025,
                "severity": "medium", "description": "Excavation for pipeline laying near Apex Organics"}
GOLDEN_TICKS = 12


@dataclass
class ScheduledEvent:
    zone: str
    type: str
    start: datetime
    end: datetime
    lat: float
    lon: float
    severity: str
    description: str
    record_id: str


class SimulationStream:
    def __init__(self, seed: int, history_end: datetime):
        self.model = WorldModel(seed)
        self.history_end = history_end
        self.golden_start = history_end + STEP
        self.overrides: dict[datetime, Overrides] = {}
        self.events: list[ScheduledEvent] = []
        self._build_history()
        self._build_golden()

    def _ov(self, ts: datetime) -> Overrides:
        return self.overrides.setdefault(ts, Overrides())

    @staticmethod
    def _floor(ts: datetime) -> datetime:
        return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)

    def _build_history(self) -> None:
        end = self.history_end
        for zone, etype, off_h, dur_h, (lat, lon), sev, desc in world.HISTORY_EVENTS:
            start = self._floor(end + timedelta(hours=off_h))
            self.events.append(ScheduledEvent(zone, etype, start, start + timedelta(hours=dur_h), lat, lon, sev, desc,
                                              f"sim-event:{zone}:{etype}:{start:%Y%m%dT%H%M}"))
        for fid, off_h, dur_h, level in world.HISTORY_FACTORY_OVERRIDES:
            t = self._floor(end + timedelta(hours=off_h))
            for i in range(int(dur_h * 4)):
                self._ov(t + i * STEP).factory_levels[fid] = level
        for zone, param, off_h, add in world.HISTORY_POINT_SPIKES:
            self._ov(self._floor(end + timedelta(hours=off_h))).point_spikes[(zone, param)] = add

    def _build_golden(self) -> None:
        for k, level in GOLDEN_FACTORY_LEVELS.items():
            self._ov(self.golden_start + k * STEP).factory_levels["fac_a1"] = level
        g = GOLDEN_EVENT
        start = self.golden_start + g["k_start"] * STEP
        self.events.append(ScheduledEvent("zone_a", g["type"], start, start + g["duration_windows"] * STEP, g["lat"],
                                          g["lon"], g["severity"], g["description"],
                                          f"sim-event:zone_a:golden:{start:%Y%m%dT%H%M}"))

    def active_event_types(self, ts: datetime) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for e in self.events:
            if e.start <= ts < e.end:
                out.setdefault(e.zone, set()).add(e.type)
        return out

    def air_water_records(self, ts: datetime) -> tuple[list[dict], list[dict]]:
        recs = self.model.sensor_readings(ts, self.overrides, self.active_event_types(ts))
        return [r for r in recs if r["source"] == "sim_air"], [r for r in recs if r["source"] == "sim_water"]

    def factory_records(self, ts: datetime) -> list[dict]:
        return self.model.factory_records(ts, self.overrides)

    def event_records(self, ts: datetime) -> list[dict]:
        """Events are published when they start (planned end time included)."""
        return [{"source": SIM_EVENTS, "source_record_id": e.record_id, "type": e.type,
                 "start_time": e.start.isoformat(), "end_time": e.end.isoformat(), "latitude": e.lat,
                 "longitude": e.lon, "severity": e.severity, "description": e.description}
                for e in self.events if ts <= e.start < ts + STEP]
