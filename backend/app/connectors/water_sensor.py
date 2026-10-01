"""Water sensor connector. No automatic live water-sensor stream is available to this prototype, so the
feed is the SIMULATED DEMO STREAM and is labelled as such everywhere (API `is_simulated`, UI badge).
A real sensor gateway would implement the same fetch() contract."""
from datetime import datetime

from app.connectors.base import ConnectorBatch, SourceInfo
from app.connectors.simulated import _run
from app.simulation.stream import SimulationStream

INFO = SourceInfo("sim_water", "Water sensor network — SIMULATED DEMO STREAM", "water", True, "observations")


def fetch(stream: SimulationStream, ts: datetime, outage: bool = False) -> ConnectorBatch:
    return _run(lambda: stream.air_water_records(ts)[1], outage, INFO.name)
