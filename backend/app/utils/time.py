"""Clock helpers. Services call these through the module (`clock.now_local()`) so tests can
freeze time with monkeypatch."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz)


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_local() -> datetime:
    return now_utc().astimezone(local_tz())


def today_local() -> date:
    """'Today' is always computed in the canteen time zone (Asia/Almaty), not UTC."""
    return now_local().date()


def combine_local(day: date, at: time) -> datetime:
    """A wall-clock time on a given day in the canteen time zone."""
    return datetime.combine(day, at, tzinfo=local_tz())
