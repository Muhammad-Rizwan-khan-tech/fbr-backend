"""Redis access, distributed locks and fixed-window rate limiting.

PostgreSQL stays the system of record. Redis is used for: the Celery broker,
worker heartbeats, queue-depth inspection, rate limiting, and short-lived
distributed locks (e.g. so only one maintenance sweeper runs at a time).

When ``REDIS_URL`` is not configured (local development / tests) every helper
degrades to a safe in-process fallback so the app still runs.
"""
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from backend.app.core.config import settings

_client = None
_client_lock = threading.Lock()


def get_redis():
    """Return a shared redis client, or ``None`` when Redis is not configured."""
    global _client
    if not settings.REDIS_URL:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                import redis

                _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=3,
                                               socket_connect_timeout=3, health_check_interval=30)
    return _client


def set_redis_for_tests(client) -> None:
    global _client
    _client = client


get_redis_client = get_redis



def reset_redis() -> None:
    global _client
    _client = None


def ping_redis() -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


@contextmanager
def redis_lock(name: str, ttl_seconds: int = 60) -> Iterator[bool]:
    """Best-effort distributed lock. Yields True if acquired.

    Without Redis the lock is considered acquired (single-process mode).
    """
    client = get_redis()
    if client is None:
        yield True
        return
    key = f"fbrcloud:lock:{name}"
    token = str(time.time_ns())
    acquired = False
    try:
        acquired = bool(client.set(key, token, nx=True, ex=ttl_seconds))
    except Exception:
        acquired = False
    try:
        yield acquired
    finally:
        if acquired:
            try:
                if client.get(key) == token:
                    client.delete(key)
            except Exception:
                pass


# ---------------------------------------------------------------------------------
# Rate limiting (fixed window)
# ---------------------------------------------------------------------------------
_local_hits: dict = {}
_local_lock = threading.Lock()


def rate_limit_allow(scope: str, identity: str, limit: int, window_seconds: int = 60) -> bool:
    """Return True if the call is within the limit."""
    if not settings.RATE_LIMIT_ENABLED or limit <= 0:
        return True
    bucket = int(time.time() // window_seconds)
    key = f"fbrcloud:rl:{scope}:{identity}:{bucket}"
    client = get_redis()
    if client is not None:
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, window_seconds + 1)
            return count <= limit
        except Exception:
            pass  # fail open if Redis hiccups; never block invoicing because of the limiter
    with _local_lock:
        # prune old buckets lazily
        for stale in [k for k in _local_hits if not k.endswith(f":{bucket}")]:
            _local_hits.pop(stale, None)
        _local_hits[key] = _local_hits.get(key, 0) + 1
        return _local_hits[key] <= limit


def reset_local_rate_limits() -> None:
    with _local_lock:
        _local_hits.clear()
