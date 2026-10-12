"""Prometheus metrics (SPEC 14.8).

- HTTP (RPS, latency, status codes): prometheus-fastapi-instrumentator on the API, `/metrics`.
  With several gunicorn processes they share PROMETHEUS_MULTIPROC_DIR (see gunicorn.conf.py).
- Business metrics are read from the database at scrape time by the worker process
  (`BusinessCollector`, port WORKER_METRICS_PORT): the counts are then the same whichever API
  process served the order, and survive restarts.
- Background jobs: duration, failures and failures in a row (alert at 3). The label is `task`,
  because Prometheus keeps `job` for the scrape target.
"""

from collections.abc import Callable, Iterator

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Canteen, Order, PickupSlot
from app.utils.time import today_local

JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Background job duration",
    ["task"],
    buckets=(0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
JOB_FAILURES = Counter("job_failures_total", "Background job failures", ["task"])
JOB_FAILING = Gauge(
    "job_consecutive_failures", "Failures in a row since the last success", ["task"]
)


def install_http_metrics(app: FastAPI) -> None:
    Instrumentator(
        excluded_handlers=["/metrics", "/api/v1/health.*"],
        should_group_status_codes=False,
    ).instrument(
        app,
        # The default buckets (0.1, 0.5, 1 s) are too coarse for a p95 target of 0.5 s.
        latency_lowr_buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 2.5, 5),
    ).expose(app, endpoint="/metrics", include_in_schema=False)


def record_job(name: str, seconds: float, ok: bool) -> None:
    JOB_DURATION.labels(task=name).observe(seconds)
    if ok:
        JOB_FAILING.labels(task=name).set(0)
    else:
        JOB_FAILURES.labels(task=name).inc()
        JOB_FAILING.labels(task=name).inc()


class BusinessCollector(Collector):
    """orders_created_total, orders_by_status (today), slot_fill_ratio (today), canteen_db_up."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def collect(self) -> Iterator[Metric]:
        up = GaugeMetricFamily("canteen_db_up", "The worker can query the database")
        try:
            metrics = list(self._business())
        except Exception:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        yield from metrics

    def _business(self) -> Iterator[Metric]:
        today = today_local()
        with self.session_factory() as db:
            created = db.scalar(select(func.count(Order.id))) or 0
            by_status = db.execute(
                select(Order.status, func.count(Order.id))
                .where(Order.service_date == today)
                .group_by(Order.status)
            ).all()
            fill = db.execute(
                select(
                    Canteen.slug, func.sum(PickupSlot.booked_count), func.sum(PickupSlot.capacity)
                )
                .join(Canteen, Canteen.id == PickupSlot.canteen_id)
                .where(PickupSlot.slot_date == today, PickupSlot.is_closed.is_(False))
                .group_by(Canteen.slug)
            ).all()
        yield CounterMetricFamily("orders_created", "Orders created since the start", value=created)
        statuses = GaugeMetricFamily(
            "orders_by_status", "Today's orders by status", labels=["status"]
        )
        for status, count in by_status:
            statuses.add_metric([status.value], count)
        yield statuses
        ratio = GaugeMetricFamily(
            "slot_fill_ratio", "Booked places / capacity of today's open slots", labels=["canteen"]
        )
        for slug, booked, capacity in fill:
            ratio.add_metric([slug], round(booked / capacity, 4) if capacity else 0.0)
        yield ratio
