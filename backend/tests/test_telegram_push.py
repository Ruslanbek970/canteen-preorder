import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
from pywebpush import WebPushException
from sqlalchemy import func, select

from app.config import get_settings
from app.models import PushSubscription, User
from app.notifications import push, service
from app.redis_client import get_redis
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import orders, telegram
from worker import jobs

DAY = date(2026, 10, 12)
SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "key", "auth": "secret"}}


# ---- Telegram ------------------------------------------------------------------------------


def test_link_code_is_one_time(db, factory, monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_bot_username", "canteen_bot")
    user = factory.user(full_name="Айгерим")
    link = telegram.create_link_code(user)
    assert len(link.code) == 6 and link.expires_in == 600
    assert link.deep_link == f"https://t.me/canteen_bot?start={link.code}"
    assert get_redis().ttl(f"tg:link:{link.code}") > 590

    assert telegram.handle_command(db, 555, f"/start {link.code}").startswith("Готово, Айгерим")
    db.refresh(user)
    assert user.telegram_chat_id == 555
    assert telegram.handle_command(db, 556, f"/start {link.code}").startswith("Код не подошёл")


def test_chat_moves_to_the_new_account(db, factory):
    first = factory.user(telegram_chat_id=900)
    second = factory.user(preferred_language="en")
    code = telegram.create_link_code(second).code
    assert telegram.handle_command(db, 900, f"/start {code}").startswith("Done,")
    db.refresh(first)
    assert first.telegram_chat_id is None
    assert telegram.user_by_chat(db, 900).id == second.id


def test_bot_commands(db, factory, freeze):
    freeze("2026-10-12 10:00")
    assert "/start 123456" in telegram.handle_command(db, 1, "/start")
    assert telegram.handle_command(db, 1, "/orders").startswith("Чат ещё не привязан")

    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:30")
    item = factory.menu_item(canteen, day=DAY)
    user = factory.user(preferred_language="kk", telegram_chat_id=42)
    assert telegram.handle_command(db, 42, "/orders") == "Белсенді тапсырыстар жоқ."
    orders.create_order(
        db,
        user,
        OrderCreate(
            canteen_id=canteen.id,
            pickup_slot_id=slot.id,
            items=[OrderItemIn(menu_item_id=item.id, quantity=1)],
        ),
    )
    text = telegram.handle_command(db, 42, "/orders@canteen_bot")
    assert text.splitlines() == ["Белсенді тапсырыстарыңыз:", "A-001 · 12:30 · төлемді күтуде"]
    assert telegram.handle_command(db, 42, "/start").startswith("Бұл чат байланыстырылған")
    assert telegram.handle_command(db, 42, "hello").startswith("Командалар")
    assert telegram.handle_command(db, 42, "/stop").startswith("Чат ажыратылды")
    db.refresh(user)
    assert user.telegram_chat_id is None


def test_telegram_api(client, auth, db, factory):
    user = factory.user(telegram_chat_id=77)
    h = auth(user)
    assert client.get("/api/v1/me", headers=h).json()["telegram_linked"] is True
    code = client.post("/api/v1/me/telegram/link-code", headers=h).json()
    assert len(code["code"]) == 6
    assert client.delete("/api/v1/me/telegram", headers=h).status_code == 204
    assert client.get("/api/v1/me", headers=h).json()["telegram_linked"] is False
    assert client.post("/api/v1/me/telegram/link-code").status_code == 401


def test_bot_idles_without_token(monkeypatch, caplog):
    from bot import main as bot_main

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "")

    async def short() -> None:
        await asyncio.wait_for(bot_main.run(), timeout=0.2)

    with caplog.at_level("WARNING", logger="bot"), pytest.raises(TimeoutError):
        asyncio.run(short())
    assert "bot is idle" in caplog.text


def test_bot_delivers_outbox(monkeypatch):
    from bot import main as bot_main

    sent: list[tuple[int, str]] = []

    class FakeBot:
        async def send_message(self, chat_id: int, text: str) -> None:
            if chat_id == 0:
                raise RuntimeError("blocked by user")
            sent.append((chat_id, text))

    class FakeRedis:
        def __init__(self) -> None:
            self.items = [
                (b"q", json.dumps({"chat_id": 0, "text": "x"}).encode()),
                None,
                (b"q", json.dumps({"chat_id": 5, "text": "hi"}).encode()),
            ]

        async def blpop(self, keys, timeout):
            if not self.items:
                raise asyncio.CancelledError
            return self.items.pop(0)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(bot_main.deliver_outbox(FakeBot(), FakeRedis()))
    assert sent == [(5, "hi")]


# ---- Web Push ------------------------------------------------------------------------------


@pytest.fixture
def vapid(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_private_key", "private")
    monkeypatch.setattr(settings, "vapid_public_key", "public")


def test_push_key_and_subscriptions_api(client, auth, db, factory, monkeypatch):
    user = factory.user()
    h = auth(user)
    monkeypatch.setattr(get_settings(), "vapid_public_key", "")
    assert client.get("/api/v1/notifications/push-key", headers=h).status_code == 404
    monkeypatch.setattr(get_settings(), "vapid_public_key", "public")
    assert client.get("/api/v1/notifications/push-key", headers=h).json() == {
        "public_key": "public"
    }

    assert client.post("/api/v1/me/push-subscriptions", json=SUB, headers=h).status_code == 204
    # Same browser, another account: the subscription moves.
    other = factory.user()
    client.post("/api/v1/me/push-subscriptions", json=SUB, headers=auth(other))
    subs = db.scalars(select(PushSubscription)).all()
    assert [s.user_id for s in subs] == [other.id]
    bad = {**SUB, "endpoint": "http://insecure"}
    assert client.post("/api/v1/me/push-subscriptions", json=bad, headers=h).status_code == 422
    r = client.request(
        "DELETE", "/api/v1/me/push-subscriptions", json={"endpoint": SUB["endpoint"]}, headers=h
    )
    assert r.status_code == 204
    assert db.scalar(select(func.count(PushSubscription.id))) == 1  # not this user's
    client.request(
        "DELETE",
        "/api/v1/me/push-subscriptions",
        json={"endpoint": SUB["endpoint"]},
        headers=auth(other),
    )
    db.expire_all()
    assert db.scalar(select(func.count(PushSubscription.id))) == 0


def _subscribe(db, user, endpoint):
    db.add(PushSubscription(user_id=user.id, endpoint=endpoint, p256dh="k", auth="a"))
    db.commit()


def test_push_delivery_drops_gone_subscriptions(db, factory, vapid, monkeypatch):
    user = factory.user()
    _subscribe(db, user, "https://push.example/ok")
    _subscribe(db, user, "https://push.example/gone")
    _subscribe(db, user, "https://push.example/flaky")
    calls: list[tuple[str, dict]] = []

    def fake_webpush(subscription_info, data, **kw):
        endpoint = subscription_info["endpoint"]
        calls.append((endpoint, json.loads(data)))
        if endpoint.endswith("gone"):
            raise WebPushException("gone", response=SimpleNamespace(status_code=410))
        if endpoint.endswith("flaky"):
            raise WebPushException("later", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(push, "webpush", fake_webpush)
    params = {"percent": 30, "dish": "Самса", "until": "15:00", "canteen": "Главная"}
    service.notify(db, db.get(User, user.id), "leftover_discount", url="/menu", **params)
    db.commit()
    assert get_redis().llen(service.PUSH_QUEUE) == 1
    assert jobs.deliver_push() == 1
    assert {c[1]["url"] for c in calls} == {"/menu"}
    assert calls[0][1]["title"] == "Скидка 30% на Самса"
    db.expire_all()
    left = db.scalars(select(PushSubscription.endpoint).order_by(PushSubscription.id)).all()
    assert left == ["https://push.example/ok", "https://push.example/flaky"]
    assert push.deliver_queued(db) == 0  # queue is empty


def test_no_push_queued_without_keys_or_subscriptions(db, factory, monkeypatch):
    user = factory.user()
    params = {"percent": 30, "dish": "Самса", "until": "15:00", "canteen": "Главная"}
    monkeypatch.setattr(get_settings(), "vapid_private_key", "private")
    service.notify(db, user, "leftover_discount", **params)  # no subscription
    db.commit()
    _subscribe(db, user, "https://push.example/1")
    monkeypatch.setattr(get_settings(), "vapid_private_key", "")
    service.notify(db, db.get(User, user.id), "leftover_discount", **params)  # no key
    db.commit()
    assert get_redis().llen(service.PUSH_QUEUE) == 0
    assert push.deliver_queued(db) == 0
