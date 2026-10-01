"""Connector contract. Every source returns raw records in its own shape; ingestion normalizes them."""
from dataclasses import dataclass, field


class ConnectorError(RuntimeError):
    """Raised when a source cannot deliver data (outage, auth, network, bad payload)."""


class ConnectorNotConfigured(ConnectorError):
    """Raised when credentials/endpoint are not configured. Reported as OFFLINE, never faked."""


@dataclass
class SourceInfo:
    name: str
    label: str
    category: str       # air | water | factory | events | reference
    is_simulated: bool
    kind: str           # observations | factory_outputs | events | none


@dataclass
class ConnectorBatch:
    records: list = field(default_factory=list)
    latency_ms: float = 0.0
