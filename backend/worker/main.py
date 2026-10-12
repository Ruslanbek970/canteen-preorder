"""python -m worker.main — the APScheduler process (SPEC 10)."""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from prometheus_client import REGISTRY, start_http_server

from app.config import get_settings
from app.db import SessionLocal
from app.logs import setup_logging
from app.metrics import BusinessCollector
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
    scheduler.add_job(jobs.forecast_tomorrow, CronTrigger(hour=2, minute=0, timezone=tz))
    return scheduler


def main() -> None:
    settings = get_settings()
    setup_logging(json=settings.app_env == "prod")
    REGISTRY.register(BusinessCollector(SessionLocal))
    start_http_server(settings.worker_metrics_port)
    jobs.generate_slots()  # «и при старте»
    jobs.expire_unpaid_orders()
    build_scheduler().start()


if __name__ == "__main__":
    main()
