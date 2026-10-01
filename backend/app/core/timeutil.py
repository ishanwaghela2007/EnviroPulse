from datetime import datetime, timedelta, timezone

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def bucket_minutes() -> int:
    return get_settings().default_time_window_minutes


def floor_bucket(ts: datetime, minutes: int | None = None) -> datetime:
    m = minutes or bucket_minutes()
    ts = to_utc(ts)
    return ts.replace(minute=(ts.minute // m) * m, second=0, microsecond=0)


def bucket_delta() -> timedelta:
    return timedelta(minutes=bucket_minutes())


TIME_RANGES = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "12h": timedelta(hours=12),
               "24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7),
               "14d": timedelta(days=14)}
