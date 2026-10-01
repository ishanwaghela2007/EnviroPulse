"""Reset the demo: truncate all data tables, clear Redis keys, reseed. Replays the golden scenario from
the start.  Usage: python -m app.seed.reset_demo"""
from sqlalchemy import text

from app.core import redis as rcache
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import configure_logging

TABLES = ["alert_events", "feedback", "alerts", "attributions", "anomalies", "forecasts", "features",
          "aqi_snapshots", "water_observations", "readings", "quarantined_records", "factory_outputs", "events",
          "thresholds", "factories", "sensors", "zones", "source_health", "pipeline_state"]


def reset(reseed: bool = True) -> dict | None:
    with session_scope() as db:
        db.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    rcache.flush_namespace()
    if reseed:
        from app.seed.seed_database import seed
        from app.services import demo_stream
        demo_stream._stream_cache.clear()
        return seed()
    return None


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    reset()
