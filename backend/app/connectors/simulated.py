"""Simulated connectors (SIMULATED DEMO STREAM). They emit raw records for one window from the
deterministic simulation stream; a configured outage makes the connector fail like a real source."""
import time
from datetime import datetime

from app.connectors.base import ConnectorBatch, ConnectorError, SourceInfo
from app.simulation.stream import SimulationStream

SIM_AIR = SourceInfo("sim_air", "Air sensor network — SIMULATED DEMO STREAM", "air", True, "observations")


def fetch_air(stream: SimulationStream, ts: datetime, outage: bool = False) -> ConnectorBatch:
    return _run(lambda: stream.air_water_records(ts)[0], outage, SIM_AIR.name)


def _run(fn, outage: bool, name: str) -> ConnectorBatch:
    t0 = time.perf_counter()
    if outage:
        raise ConnectorError(f"{name}: simulated outage (connection timed out)")
    records = fn()
    return ConnectorBatch(records, (time.perf_counter() - t0) * 1000)
