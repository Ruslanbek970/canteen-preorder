import json
from datetime import date

import pytest
from sqlalchemy import func, select, update

from app.config import get_settings
from app.i18n.messages import TEMPLATES, render
from app.models import Notification, Order, OrderStatus, User, UserRole
from app.notifications import service
from app.redis_client import get_redis
from app.schemas.orders import OrderCreate, OrderItemIn
from app.security import create_access_token
from app.services import loyalty, orders, payments
from app.services.order_status import Actor, change_status
from worker import jobs

DAY = date(2026, 10, 12)


@pytest.fixture
def n(factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:00")
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", price=1550), day=DAY, portions=20
    )
    return {"canteen": canteen, "slot": slot, "plov": plov}


def place(db, n, user, qty=1):
    out = orders.create_order(
        db,
        user,
        OrderCreate(
            canteen_id=n["canteen"].id,
            pickup_slot_id=n["slot"].id,
            items=[OrderItemIn(menu_item_id=n["plov"].id, quantity=qty)],
        ),
    )
    return db.get(Order, out.id), out.payment_id


def kinds(db, user):
    return db.scalars(
        select(Notification.kind).where(Notification.user_id == user.id).order_by(Notification.id)
    ).all()


def test_templates_have_every_language():
    for kind, texts in TEMPLATES.items():
        assert set(texts) == {"ru", "kk", "en"}, kind
    msg = render("order_ready", "kk", number="A-001", shelf=3)
    assert msg.title == "A-001 тапсырысы дайын" and "3" in msg.body
    assert render("order_ready", "xx", number="A-1", shelf=1).title == "Заказ A-1 готов"


def test_order_lifecycle_notifies_in_user_language(db, factory, n):
    user = factory.user(preferred_language="en")
    order, payment_id = place(db, n, user, qty=2)
    payments.settle(db, payment_id, True, "n-1")
    db.refresh(order)
    change_status(db, order, OrderStatus.cooking, Actor.kitchen)
    change_status(db, order, OrderStatus.ready, Actor.kitchen, pickup_shelf=4)
    db.commit()
    notes = db.scalars(select(Notification).where(Notification.user_id == user.id)).all()
    assert [x.kind for x in notes] == ["order_paid", "order_ready"]
    assert notes[0].title == "Order A-001 is paid" and "12:00" in notes[0].body
    assert notes[1].body == "Pick it up from shelf 4."
    assert all(x.channel == "in_app" and x.order_id == order.id for x in notes)

    change_status(db, order, OrderStatus.picked_up, Actor.pickup)
    db.commit()
    db.refresh(user)
    assert user.loyalty_points == 31  # 3100 ₸ -> 31 points


def test_cancel_notifies_and_till_sale_does_not(db, factory, n):
    user = factory.user()
    order, _ = place(db, n, user)
    orders.cancel_order(db, user, order.id)
    assert kinds(db, user) == ["order_cancelled"]


def test_loyalty_points():
    from decimal import Decimal

    assert loyalty.points_for(Decimal("99")) == 0
    assert loyalty.points_for(Decimal("1550")) == 15


def test_slot_reminder_once_five_minutes_before(db, factory, n, freeze):
    user = factory.user()
    order, payment_id = place(db, n, user)
    payments.settle(db, payment_id, True, "n-2")
    unpaid_user = factory.user()
    place(db, n, unpaid_user)
    freeze("2026-10-12 11:54")
    assert service.slot_reminders(db) == 0
    freeze("2026-10-12 11:56")
    assert jobs.slot_reminders() == 1
    assert service.slot_reminders(db) == 0
    assert kinds(db, user) == ["order_paid", "slot_reminder"]
    assert kinds(db, unpaid_user) == []
    note = db.scalar(select(Notification).where(Notification.kind == "slot_reminder"))
    assert note.title == "Скоро выдача: A-001"


def test_marketing_respects_opt_out(db, factory):
    yes = factory.user()
    no = factory.user(marketing_opt_out=True)
    params = {"percent": 30, "dish": "Самса", "until": "15:00", "canteen": "Главная"}
    assert service.notify(db, yes, "leftover_discount", **params) is not None
    assert service.notify(db, no, "leftover_discount", **params) is None
    db.commit()
    assert db.scalar(select(func.count(Notification.id))) == 1


def test_external_deliveries_are_queued_after_commit(db, factory, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    user = factory.user(telegram_chat_id=777)
    params = {"percent": 30, "dish": "Самса", "until": "15:00", "canteen": "Главная"}
    service.notify(db, user, "leftover_discount", **params)
    redis = get_redis()
    assert redis.llen(service.TELEGRAM_QUEUE) == 0  # nothing before commit
    db.commit()
    queued = json.loads(redis.lpop(service.TELEGRAM_QUEUE))
    assert queued["chat_id"] == 777 and queued["text"].startswith("Скидка 30% на Самса")
    # A rollback drops the queued delivery.
    service.notify(db, user, "leftover_discount", **params)
    db.rollback()
    assert redis.llen(service.TELEGRAM_QUEUE) == 0
    # No token: nothing is queued for Telegram.
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    service.notify(db, user, "leftover_discount", **params)
    db.commit()
    assert redis.llen(service.TELEGRAM_QUEUE) == 0


def test_notifications_api(client, auth, db, factory, n):
    user = factory.user()
    order, payment_id = place(db, n, user)
    payments.settle(db, payment_id, True, "n-3")
    db.execute(update(Order).where(Order.id == order.id).values(status=OrderStatus.cancelled))
    db.commit()
    h = auth(user)
    data = client.get("/api/v1/notifications", headers=h).json()
    assert data["unread"] == 1 and data["items"][0]["kind"] == "order_paid"
    note_id = data["items"][0]["id"]
    other = auth(factory.user())
    assert client.post(f"/api/v1/notifications/{note_id}/read", headers=other).status_code == 404
    r = client.post(f"/api/v1/notifications/{note_id}/read", headers=h)
    assert r.status_code == 200 and r.json()["read_at"] is not None
    assert client.get("/api/v1/notifications", headers=h).json()["unread"] == 0
    service.notify(
        db, db.get(User, user.id), "leftover_discount", percent=1, dish="x", until="y", canteen="z"
    )
    db.commit()
    assert client.post("/api/v1/notifications/read-all", headers=h).json() == {"marked": 1}
    assert client.get("/api/v1/notifications").status_code == 401


def test_ws_me_gets_new_notifications(client, db, factory, n):
    user = factory.user()
    order, payment_id = place(db, n, user)
    token = create_access_token(user)
    with client.websocket_connect(f"/ws/me?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"
        payments.settle(db, payment_id, True, "n-4")
        seen = [ws.receive_json()["type"], ws.receive_json()["type"]]
    assert seen == ["order.paid", "notification.new"]


def test_staff_get_notifications_too(client, auth, factory):
    cook = factory.user(UserRole.cook)
    assert client.get("/api/v1/notifications", headers=auth(cook)).json() == {
        "items": [],
        "unread": 0,
    }
