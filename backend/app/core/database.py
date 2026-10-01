from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Used by tests to point the app at a different database."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def SessionLocal() -> Session:
    get_engine()
    return _SessionLocal()  # type: ignore[misc]


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            postgis = conn.execute(text("SELECT postgis_lib_version()")).scalar()
            timescale = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
            ).scalar()
        return {"status": "ok", "postgis": postgis, "timescaledb": timescale or "not installed"}
    except Exception as exc:  # pragma: no cover - reported, not raised
        return {"status": "error", "error": type(exc).__name__}


PIPELINE_LOCK_KEY = 771313


def pipeline_lock(db) -> None:
    """Serialise pipeline mutations (demo ticks, watermark processing, outage toggles) across API requests,
    worker jobs and processes. Transaction-scoped PostgreSQL advisory lock: released on commit/rollback and
    re-entrant within the same transaction, so nested calls are safe."""
    from sqlalchemy import text as _text
    db.execute(_text("SELECT pg_advisory_xact_lock(:k)"), {"k": PIPELINE_LOCK_KEY})
