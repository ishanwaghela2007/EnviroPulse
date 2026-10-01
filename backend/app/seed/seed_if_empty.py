"""Container start-up helper: seed the demo data only when the database has no zones yet, so restarting
the stack never wipes operator feedback or alert history.  Usage: python -m app.seed.seed_if_empty"""
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import configure_logging


def main() -> None:
    configure_logging(get_settings().log_level)
    with session_scope() as db:
        seeded = db.execute(text("SELECT count(*) FROM zones")).scalar()
    if seeded:
        print(f"Database already has {seeded} zones; skipping seed.")
        return
    from app.seed.seed_database import seed
    seed()


if __name__ == "__main__":
    main()
