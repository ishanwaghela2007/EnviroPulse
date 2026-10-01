"""Factory output connector: seeded/simulated production_level (%) and operating state per facility."""
from datetime import datetime

from app.connectors.base import ConnectorBatch, SourceInfo
from app.connectors.simulated import _run
from app.simulation.stream import SimulationStream

INFO = SourceInfo("sim_factory", "Factory operations feed — SIMULATED DEMO STREAM", "factory", True,
                  "factory_outputs")


def fetch(stream: SimulationStream, ts: datetime, outage: bool = False) -> ConnectorBatch:
    return _run(lambda: stream.factory_records(ts), outage, INFO.name)
