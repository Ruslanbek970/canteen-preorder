from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz)


def now_local() -> datetime:
    return datetime.now(local_tz())


def today_local() -> date:
    """'Today' is always computed in the canteen time zone (Asia/Almaty), not UTC."""
    return now_local().date()
