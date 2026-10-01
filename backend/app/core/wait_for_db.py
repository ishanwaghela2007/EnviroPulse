"""Block until PostgreSQL accepts connections (used by the container entrypoint)."""
import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main(timeout_s: int = 90) -> int:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready.")
            return 0
        except Exception as exc:  # noqa: BLE001 - any connection error means "not ready yet"
            print(f"Waiting for database… ({type(exc).__name__})")
            time.sleep(2)
    print("Database did not become ready in time.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
