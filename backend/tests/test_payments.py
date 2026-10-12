import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.models import MenuItem, Order, OrderStatus, Payment, PaymentStatus, PickupSlot, UserRole
from app.redis_client import get_redis
from app.security import create_access_token
from app.services import orders as order_service
from app.services import payments
from app.utils import time as clock
from worker import jobs

DAY = date(2026, 10, 12)


@pytest.fixture
def ctx(factory, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:00")
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", price=1500), day=DAY, portions=10
    )
    return {"canteen": canteen, "slot": slot, "plov": plov, "user": factory.user()}


def place(client, auth, ctx, qty=2):
    r = client.post(
        "/api/v1/orders",
        json={
            "canteen_id": ctx["canteen"].id,
            "pickup_slot_id": ctx["slot"].id,
            "items": [{"menu_item_id": ctx["plov"].id, "quantity": qty}],
        },
        headers=auth(ctx["user"]),
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_pending_payment_to_paid(client, auth, ctx, db):
    """SPEC phase 4 'done when': pending_payment -> paid."""
    order = place(client, auth, ctx)
    assert order["payment_url"] == f"/pay/mock/{order['payment_id']}"
    h = auth(ctx["user"])

    page = client.get(f"/api/v1/payments/{order['payment_id']}", headers=h).json()
    assert Decimal(page["amount"]) == Decimal("3000") and page["order_number"] == "A-001"

    r = client.post(f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "succeeded"
    assert r.json()["fiscal_receipt_number"].startswith("MOCK-")

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=h).json()
    assert detail["status"] == "paid"
    assert detail["paid_at"] is not None
    assert detail["payment_url"] is None
    payment = db.get(Payment, order["payment_id"])
    assert payment.provider_transaction_id.startswith("mock-")

    # A repeated success is harmless; a failure after success is refused.
    assert (
        client.post(f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=h).status_code
        == 200
    )
    r = client.post(f"/api/v1/payments/mock/{order['payment_id']}/fail", headers=h)
    assert r.status_code == 409


def test_fail_then_pay_again(client, auth, ctx):
    order = place(client, auth, ctx)
    h = auth(ctx["user"])
    r = client.post(f"/api/v1/payments/mock/{order['payment_id']}/fail", headers=h)
    assert r.json()["status"] == "failed"
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=h).json()
    assert detail["status"] == "pending_payment" and detail["payment_url"] is None

    retry = client.post(f"/api/v1/orders/{order['id']}/pay", headers=h).json()
    assert retry["id"] != order["payment_id"] and retry["url"] == f"/pay/mock/{retry['id']}"
    # Asking again reuses the open payment.
    again = client.post(f"/api/v1/orders/{order['id']}/pay", headers=h).json()
    assert again["id"] == retry["id"]
    client.post(f"/api/v1/payments/mock/{retry['id']}/confirm", headers=h)
    assert client.get(f"/api/v1/orders/{order['id']}", headers=h).json()["status"] == "paid"
    r = client.post(f"/api/v1/orders/{order['id']}/pay", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "order_not_payable"


def test_foreign_payment_is_hidden(client, auth, ctx, factory):
    order = place(client, auth, ctx)
    stranger = auth(factory.user())
    pid = order["payment_id"]
    assert client.get(f"/api/v1/payments/{pid}", headers=stranger).status_code == 404
    assert client.post(f"/api/v1/payments/mock/{pid}/confirm", headers=stranger).status_code == 404
    cook = auth(factory.user(UserRole.cook))
    assert client.post(f"/api/v1/payments/mock/{pid}/confirm", headers=cook).status_code == 403


def test_public_mock_webhook_is_closed(client):
    r = client.post("/api/v1/payments/webhook/mock", json={"payment_id": 1, "succeeded": True})
    assert r.status_code == 404


def _age(db, order_id: int, minutes: int) -> None:
    db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(created_at=clock.now_utc() - timedelta(minutes=minutes))
    )
    db.commit()


def test_expire_unpaid_returns_portions_and_is_idempotent(client, auth, ctx, db):
    """SPEC phase 4 'done when': an unpaid order is cancelled after 10 minutes."""
    old = place(client, auth, ctx, qty=3)
    fresh = place(client, auth, ctx, qty=1)
    _age(db, old["id"], 11)
    _age(db, fresh["id"], 5)

    assert order_service.expire_unpaid_orders(db) == 1
    assert order_service.expire_unpaid_orders(db) == 0
    db.expire_all()
    assert db.get(Order, old["id"]).status == OrderStatus.cancelled
    assert db.get(Order, fresh["id"]).status == OrderStatus.pending_payment
    assert db.get(MenuItem, ctx["plov"].id).available_portions == 9
    assert db.get(PickupSlot, ctx["slot"].id).booked_count == 1
    assert db.get(Payment, old["payment_id"]).status == PaymentStatus.failed


def test_expired_order_cannot_be_paid(client, auth, ctx, db):
    order = place(client, auth, ctx)
    _age(db, order["id"], 11)
    jobs.expire_unpaid_orders()
    r = client.post(
        f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=auth(ctx["user"])
    )
    assert r.status_code == 409
    db.expire_all()
    assert db.get(Payment, order["payment_id"]).status == PaymentStatus.failed


def test_late_success_is_refunded(client, auth, ctx, db):
    """The provider reports success after the order was cancelled: the money goes back."""
    order = place(client, auth, ctx)
    db.execute(update(Order).where(Order.id == order["id"]).values(status=OrderStatus.cancelled))
    db.commit()
    with pytest.raises(Exception) as exc:
        payments.settle(db, order["payment_id"], True, "late-1")
    assert getattr(exc.value, "code", None) == "order_not_payable"
    db.expire_all()
    assert db.get(Payment, order["payment_id"]).status == PaymentStatus.refunded


def test_paid_cancel_refunds(client, auth, ctx, db):
    order = place(client, auth, ctx)
    h = auth(ctx["user"])
    client.post(f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=h)
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=h)
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Payment, order["payment_id"]).status == PaymentStatus.refunded


def test_events_are_published_after_commit_only(client, auth, ctx, db):
    pubsub = get_redis().pubsub()
    pubsub.subscribe(f"ws:user:{ctx['user'].id}", f"ws:kitchen:{ctx['canteen'].id}")
    pubsub.get_message(timeout=1)
    pubsub.get_message(timeout=1)
    order = place(client, auth, ctx)
    # A failing order publishes nothing.
    client.post(
        "/api/v1/orders",
        json={
            "canteen_id": ctx["canteen"].id,
            "pickup_slot_id": ctx["slot"].id,
            "items": [{"menu_item_id": ctx["plov"].id, "quantity": 10}],
        },
        headers=auth(ctx["user"]),
    )
    client.post(f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=auth(ctx["user"]))
    seen = []
    while (message := pubsub.get_message(timeout=0.5)) is not None:
        if message["type"] == "message":
            seen.append((message["channel"].decode().split(":")[1], json.loads(message["data"])))
    pubsub.close()
    kinds = [(who, m["type"]) for who, m in seen]
    assert kinds == [
        ("user", "order.created"),
        ("kitchen", "order.created"),
        ("user", "order.paid"),
        ("kitchen", "order.paid"),
    ]
    assert seen[2][1]["data"]["status"] == "paid"
    assert "allergens" not in json.dumps(seen)


def test_ws_me_receives_own_order_updates(client, auth, ctx):
    order = place(client, auth, ctx)
    token = create_access_token(ctx["user"])
    with client.websocket_connect(f"/ws/me?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"
        client.post(
            f"/api/v1/payments/mock/{order['payment_id']}/confirm", headers=auth(ctx["user"])
        )
        message = ws.receive_json()
        assert message["type"] == "order.paid"
        assert message["data"]["order_id"] == order["id"]


def test_ws_rejects_bad_token_and_foreign_kitchen(client, factory):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/me?token=nope") as ws:
        ws.receive_json()
    cook = factory.user(UserRole.cook)
    other = factory.canteen()
    token = create_access_token(cook)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/ws/kitchen/{other.id}?token={token}") as ws,
    ):
        ws.receive_json()
    with client.websocket_connect(f"/ws/kitchen/{cook.canteen_id}?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"


def test_worker_job_logs_and_survives_errors(monkeypatch, caplog):
    def boom(db):
        raise RuntimeError("db down")

    monkeypatch.setattr(order_service, "expire_unpaid_orders", boom)
    with caplog.at_level("INFO", logger="worker"):
        assert jobs.expire_unpaid_orders() is None
    assert "failed" in caplog.text


def test_scheduler_has_jobs():
    from worker.main import build_scheduler

    names = {j.func.__name__ for j in build_scheduler().get_jobs()}
    assert names == {
        "generate_slots",
        "expire_unpaid_orders",
        "mark_no_show",
        "slot_reminders",
        "propose_leftover_discounts",
        "suggest_off_peak",
        "expire_promotions",
        "deliver_push",
        "forecast_tomorrow",
    }
