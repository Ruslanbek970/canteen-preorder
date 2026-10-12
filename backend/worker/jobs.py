"""Background jobs (SPEC 10). Each job opens its own session, is idempotent and logs its start,
result and duration."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from app.db import SessionLocal
from app.services import orders, pickup, slots

log = logging.getLogger("worker")


def job(fn: Callable[..., Any]) -> Callable[[], Any]:
    @wraps(fn)
    def run() -> Any:
        started = time.monotonic()
        log.info("job %s started", fn.__name__)
        try:
            with SessionLocal() as db:
                result = fn(db)
        except Exception:
            log.exception("job %s failed", fn.__name__)
            return None
        log.info("job %s done: %s (%.2fs)", fn.__name__, result, time.monotonic() - started)
        return result

    return run


@job
def generate_slots(db) -> int:
    return slots.generate_for_active(db)


@job
def expire_unpaid_orders(db) -> int:
    return orders.expire_unpaid_orders(db)


@job
def mark_no_show(db) -> int:
    return pickup.mark_no_show(db)
