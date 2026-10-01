"""Redis is used for (1) last-known-good source cache, (2) a pipeline data-version
counter the frontend polls to know when to refresh, (3) short-lived response cache,
(4) pub/sub update events. Redis is optional: every call degrades to a no-op and
health reports the outage instead of crashing the API."""
import json
import logging
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
UPDATES_CHANNEL = "enviropulse:updates"
_client: redis.Redis | None = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=1, socket_connect_timeout=1,
                                       decode_responses=True)
    return _client


def check_redis() -> dict:
    try:
        client().ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}


def cache_get(key: str) -> Any | None:
    try:
        raw = client().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        client().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.debug("redis cache_set skipped")


def bump_data_version(payload: dict) -> int | None:
    try:
        v = client().incr("enviropulse:data_version")
        client().publish(UPDATES_CHANNEL, json.dumps({**payload, "data_version": v}, default=str))
        return int(v)
    except Exception:
        return None


def data_version() -> int | None:
    try:
        v = client().get("enviropulse:data_version")
        return int(v) if v else 0
    except Exception:
        return None


def flush_namespace() -> None:
    try:
        for key in client().scan_iter("enviropulse:*"):
            client().delete(key)
        for key in client().scan_iter("lkg:*"):
            client().delete(key)
        for key in client().scan_iter("cache:*"):
            client().delete(key)
    except Exception:
        pass
