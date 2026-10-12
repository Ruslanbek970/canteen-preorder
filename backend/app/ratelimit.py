"""Fixed-window rate limiting in Redis (SPEC 12). Fails open if Redis is down."""

import logging

from app.config import get_settings
from app.errors import RateLimitedError
from app.redis_client import get_redis

log = logging.getLogger(__name__)


def hit(key: str, limit: int, window_seconds: int = 60) -> None:
    if not get_settings().rate_limit_enabled:
        return
    full_key = f"ratelimit:{key}"
    try:
        redis = get_redis()
        count = redis.incr(full_key)
        if count == 1:
            redis.expire(full_key, window_seconds)
    except Exception:  # pragma: no cover - Redis outage must not block users
        log.warning("rate limiter unavailable, allowing request", exc_info=True)
        return
    if int(count) > limit:
        raise RateLimitedError(
            "rate_limited", "Too many requests, try again in a minute", {"limit": limit}
        )


def check(key: str, limit: int) -> None:
    """Raise if `key` already used up its limit, without counting this request."""
    if not get_settings().rate_limit_enabled:
        return
    try:
        count = get_redis().get(f"ratelimit:{key}")
    except Exception:  # pragma: no cover
        return
    if count is not None and int(count) >= limit:
        raise RateLimitedError(
            "rate_limited", "Too many requests, try again in a minute", {"limit": limit}
        )
