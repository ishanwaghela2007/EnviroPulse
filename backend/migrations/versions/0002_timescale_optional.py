"""Optional TimescaleDB hypertable for readings.

If the timescaledb extension is available on the server (e.g. the timescale/timescaledb-ha image used
in docker-compose), `readings` becomes a hypertable partitioned on `timestamp`. On plain
PostgreSQL/PostGIS the same logical schema is kept with B-tree indexes on (timestamp, zone_id, parameter).

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    available = bind.execute(text("SELECT 1 FROM pg_available_extensions WHERE name='timescaledb'")).scalar()
    if not available:
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("SELECT create_hypertable('readings', 'timestamp', migrate_data => true, if_not_exists => true)")


def downgrade() -> None:
    # A hypertable cannot be converted back to a plain table in place; intentionally a no-op.
    pass
