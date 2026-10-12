import json
import logging

from prometheus_client import CollectorRegistry, generate_latest
from sqlalchemy.exc import OperationalError

from app.logs import setup_logging
from app.metrics import JOB_FAILING, JOB_FAILURES, BusinessCollector, record_job
from app.models import Order, OrderStatus
from worker import jobs


def test_request_id_is_returned_and_kept(client):
    r = client.get("/api/v1/health")
    assert len(r.headers["x-request-id"]) == 32
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    bad = client.get("/api/v1/health", headers={"X-Request-ID": "a b\tc"})
    assert bad.headers["x-request-id"] != "a b\tc"


def test_http_metrics(client):
    client.get("/api/v1/canteens")
    text = client.get("/metrics").text
    assert 'http_requests_total{handler="/api/v1/canteens",method="GET",status="200"}' in text
    assert "http_request_duration_seconds_bucket" in text
    assert "/metrics" not in client.get("/api/openapi.json").text


def test_json_logs_carry_the_request_id(client, capsys):
    setup_logging(json=True)
    try:
        client.get("/api/v1/canteens", headers={"X-Request-ID": "req-42"})
        logging.getLogger("app.test").info("outside a request")
        lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    finally:
        setup_logging(json=False)
    access = next(x for x in lines if x["event"] == "request")
    assert access["request_id"] == "req-42" and access["path"] == "/api/v1/canteens"
    assert access["status"] == 200 and access["level"] == "info"
    plain = next(x for x in lines if x["event"] == "outside a request")
    assert "request_id" not in plain and plain["logger"] == "app.test"


def test_business_metrics(db, factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen(slug="main")
    slot = factory.slot(canteen, starts="12:00", capacity=10, booked=2)
    for n, status in enumerate((OrderStatus.paid, OrderStatus.ready)):
        db.add(
            Order(
                pickup_slot_id=slot.id,
                user_id=factory.user().id,
                canteen_id=canteen.id,
                service_date=slot.slot_date,
                order_number=f"A-{n:03d}",
                status=status,
                subtotal=500,
                channel="mobile_app",
            )
        )
    db.commit()
    registry = CollectorRegistry()
    registry.register(BusinessCollector(lambda: db))
    text = generate_latest(registry).decode()
    assert "canteen_db_up 1.0" in text
    assert "orders_created_total 2.0" in text
    assert 'orders_by_status{status="paid"} 1.0' in text
    assert 'slot_fill_ratio{canteen="main"} 0.2' in text


def test_db_down_metric():
    def broken():
        raise OperationalError("SELECT 1", {}, Exception("down"))

    registry = CollectorRegistry()
    registry.register(BusinessCollector(broken))
    assert "canteen_db_up 0.0" in generate_latest(registry).decode()


def test_job_metrics_count_failures_in_a_row():
    calls = {"n": 0}

    @jobs.job
    def flaky(db):
        calls["n"] += 1
        if calls["n"] < 4:
            raise RuntimeError("boom")
        return 1

    for _ in range(3):
        assert flaky() is None
    assert JOB_FAILING.labels(task="flaky")._value.get() == 3
    assert JOB_FAILURES.labels(task="flaky")._value.get() == 3
    assert flaky() == 1
    assert JOB_FAILING.labels(task="flaky")._value.get() == 0
    record_job("other", 0.5, ok=True)
