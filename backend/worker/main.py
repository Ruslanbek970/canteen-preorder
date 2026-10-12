"""python -m worker.main — the APScheduler process (SPEC 10)."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from worker import jobs


def build_scheduler() -> BlockingScheduler:
    tz = get_settings().tz
    scheduler = BlockingScheduler(timezone=tz, job_defaults={"coalesce": True, "max_instances": 1})
    scheduler.add_job(jobs.generate_slots, CronTrigger(hour=5, minute=0, timezone=tz))
    scheduler.add_job(jobs.expire_unpaid_orders, IntervalTrigger(minutes=1))
    scheduler.add_job(jobs.mark_no_show, IntervalTrigger(minutes=5))
    scheduler.add_job(jobs.slot_reminders, IntervalTrigger(minutes=1))
    # «каждые 30 минут с 13:30 до закрытия»: the job itself skips before 13:30 and after closing.
    scheduler.add_job(
        jobs.propose_leftover_discounts, CronTrigger(hour="13-22", minute="0,30", timezone=tz)
    )
    scheduler.add_job(jobs.suggest_off_peak, CronTrigger(minute="0,30", timezone=tz))
    scheduler.add_job(jobs.expire_promotions, IntervalTrigger(minutes=10))
    scheduler.add_job(jobs.deliver_push, IntervalTrigger(seconds=15))
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    jobs.generate_slots()  # «и при старте»
    jobs.expire_unpaid_orders()
    build_scheduler().start()


if __name__ == "__main__":
    main()
