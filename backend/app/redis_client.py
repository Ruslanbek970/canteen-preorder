from functools import lru_cache

from redis import Redis

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)


def check_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
