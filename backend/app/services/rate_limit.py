import os
import time
from dataclasses import dataclass


@dataclass
class RateLimitExceeded(Exception):
    retry_after_seconds: int


@dataclass
class _Bucket:
    count: int
    reset_at: float


_buckets: dict[str, _Bucket] = {}


def _setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def check_rate_limit(key: str, *, limit: int | None = None, window_seconds: int | None = None) -> None:
    limit = limit if limit is not None else _setting("RESEARCH_GENERATE_LIMIT", 5)
    window_seconds = window_seconds if window_seconds is not None else _setting("RESEARCH_GENERATE_WINDOW_SECONDS", 3600)
    if limit <= 0 or window_seconds <= 0:
        return

    now = time.time()
    bucket = _buckets.get(key)
    if bucket is None or bucket.reset_at <= now:
        _buckets[key] = _Bucket(count=1, reset_at=now + window_seconds)
        return

    if bucket.count >= limit:
        raise RateLimitExceeded(max(1, int(bucket.reset_at - now)))

    bucket.count += 1


def clear_rate_limits() -> None:
    _buckets.clear()
