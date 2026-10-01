"""Tests run against a real PostgreSQL/PostGIS test database (TEST_DATABASE_URL) and Redis DB 1.
Schema is created with the Alembic migrations (never ad-hoc SQL); data with the real seed pipeline."""
import os

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://enviro:enviro@localhost:5433/enviropulse_test")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/1")
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ENABLE_DEMO_CONTROLS"] = "true"
os.environ["HISTORY_DAYS"] = "7"      # shorter history keeps the suite fast; still > forecast minimum (3 days)
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import reset_engine, session_scope  # noqa: E402

get_settings.cache_clear()
reset_engine()


def _migrate():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def seeded():
    """Fresh schema via migrations + full seed through the real ingestion/analytics pipeline."""
    _migrate()
    from app.seed.reset_demo import reset
    return reset(reseed=True)


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(seeded):
    with session_scope() as s:
        yield s
