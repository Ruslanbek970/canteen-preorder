"""Background jobs (SPEC 10). Each job opens its own session, is idempotent and logs its start,
result and duration."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from app.db import SessionLocal
from app.metrics import record_job
from app.notifications import push
from app.notifications import service as notifications
from app.services import orders, pickup, promotions, slots

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
            record_job(fn.__name__, time.monotonic() - started, ok=False)
            return None
        seconds = time.monotonic() - started
        log.info("job %s done: %s (%.2fs)", fn.__name__, result, seconds)
        record_job(fn.__name__, seconds, ok=True)
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


@job
def slot_reminders(db) -> int:
    return notifications.slot_reminders(db)


@job
def propose_leftover_discounts(db) -> int:
    return promotions.propose_leftover(db)


@job
def suggest_off_peak(db) -> int:
    return promotions.suggest_off_peak(db)


@job
def expire_promotions(db) -> int:
    return promotions.expire_promotions(db)


@job
def deliver_push(db) -> int:
    return push.deliver_queued(db)


@job
def forecast_tomorrow(db) -> int:
    # Imported here: scikit-learn is heavy and only this job needs it.
    from ml import forecast

    return forecast.forecast_upcoming(db)
