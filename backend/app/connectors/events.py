"""Local event connector: seeded/simulated event records (industrial_activity, construction,
traffic_event, local_event) with start/end time, location and severity."""
from datetime import datetime

from app.connectors.base import ConnectorBatch, SourceInfo
from app.connectors.simulated import _run
from app.simulation.stream import SimulationStream

INFO = SourceInfo("sim_events", "Local events register — SIMULATED DEMO STREAM", "events", True, "events")


def fetch(stream: SimulationStream, ts: datetime, outage: bool = False) -> ConnectorBatch:
    return _run(lambda: stream.event_records(ts), outage, INFO.name)
