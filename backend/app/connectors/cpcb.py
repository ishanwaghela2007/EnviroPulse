"""CPCB (Central Pollution Control Board) — official monitoring CONTEXT only.

This prototype does not call any CPCB endpoint: no public, documented, machine-readable real-time API is
configured, and the spec forbids inventing endpoints. CPCB material is used as reference context
(NAQI breakpoints, NAAQS limits and water-quality criteria cited in threshold `basis` text). CPCB water
datasets are not treated as real-time."""
from app.connectors.base import ConnectorNotConfigured, SourceInfo

INFO = SourceInfo("cpcb", "CPCB monitoring resources (reference context)", "reference", False, "none")
STATUS_MESSAGE = ("Reference context only: NAQI breakpoints and NAAQS/water criteria used for thresholds. "
                  "No machine-readable CPCB API is configured, so no CPCB data is fetched.")


def fetch(*_args, **_kwargs):
    raise ConnectorNotConfigured(STATUS_MESSAGE)
