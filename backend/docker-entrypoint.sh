#!/bin/sh
# Start-up order: wait for PostgreSQL -> apply Alembic migrations -> seed demo data once -> start the API.
set -e
python -m app.core.wait_for_db
alembic upgrade head
if [ "${SEED_ON_START:-true}" = "true" ]; then
  python -m app.seed.seed_if_empty
fi
if [ "${1:-api}" = "migrate-only" ]; then
  exit 0
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
