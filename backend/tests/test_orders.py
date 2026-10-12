import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select

from app.db import SessionLocal
from app.errors import ConflictError, DomainError
from app.models import (
    AllergySeverity,
    MenuItem,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentStatus,
    PickupSlot,
    Promotion,
    PromotionStatus,
    PromotionType,
    User,
    UserRole,
)
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import order_status, orders
from app.services.order_status import TRANSITIONS, Actor, change_status
from app.utils import time as clock

DAY = date(2026, 10, 12)


@pytest.fixture
def setup(factory, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:00", capacity=30)
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", price=1500), day=DAY, portions=20
    )
    tea = factory.menu_item(canteen, factory.dish(name_ru="Чай", price=150), day=DAY, portions=50)
    return {"canteen": canteen, "slot": slot, "plov": plov, "tea": tea}


def body(setup, *lines, ack=False, slot=None):
    return {
        "canteen_id": setup["canteen"].id,
        "pickup_slot_id": (slot or setup["slot"]).id,
        "items": [{"menu_item_id": mi.id, "quantity": q} for mi, q in lines],
        "allergy_warning_ack": ack,
    }


def place(client, auth, user, payload):
    return client.post("/api/v1/orders", json=payload, headers=auth(user))


def test_order_takes_portions_books_slot_and_numbers(client, factory, auth, setup, db):
    user = factory.user()
    r = place(client, auth, user, body(setup, (setup["plov"], 2), (setup["tea"], 1)))
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["order_number"] == "A-001"
    assert order["status"] == "pending_payment"
    assert Decimal(order["subtotal"]) == Decimal("3150")
    assert Decimal(order["total"]) == Decimal("3150")
    assert order["can_cancel"] is True
    assert order["pickup_slot"]["starts_at"] == "12:00:00"

    db.expire_all()
    assert db.get(MenuItem, setup["plov"].id).available_portions == 18
    assert db.get(MenuItem, setup["tea"].id).available_portions == 49
    assert db.get(PickupSlot, setup["slot"].id).booked_count == 1
    payment = db.scalar(select(Payment).where(Payment.order_id == order["id"]))
    assert payment.status == PaymentStatus.pending and payment.amount == Decimal("3150")
    history = db.scalars(select(OrderStatusHistory.to_status)).all()
    assert history == [OrderStatus.pending_payment]

    second = place(client, auth, factory.user(), body(setup, (setup["tea"], 1))).json()
    assert second["order_number"] == "A-002"


def test_totals_with_leftover_and_off_peak_discounts(client, factory, auth, setup, db):
    now = clock.now_utc()
    db.add_all(
        [
            Promotion(
                type=PromotionType.leftover,
                menu_item_id=setup["plov"].id,
                discount_percent=15,
                valid_from=now - timedelta(hours=1),
                valid_to=now + timedelta(hours=5),
                status=PromotionStatus.active,
            ),
            Promotion(
                type=PromotionType.off_peak,
                pickup_slot_id=setup["slot"].id,
                discount_percent=10,
                valid_from=now - timedelta(hours=1),
                valid_to=now + timedelta(hours=5),
                status=PromotionStatus.active,
            ),
        ]
    )
    db.commit()
    order = place(
        client, auth, factory.user(), body(setup, (setup["plov"], 2), (setup["tea"], 3))
    ).json()
    lines = {i["name_ru"]: i for i in order["items"]}
    # Плов: the biggest discount wins (15%): 1500 -> 1275 each.
    assert Decimal(lines["Плов"]["discount_amount"]) == Decimal("450")
    # Чай: off-peak 10%: 150 -> 135 each.
    assert Decimal(lines["Чай"]["discount_amount"]) == Decimal("45")
    assert Decimal(order["subtotal"]) == Decimal("3450")
    assert Decimal(order["discount_total"]) == Decimal("495")
    assert Decimal(order["total"]) == Decimal("2955")


def test_client_cannot_set_prices(client, factory, auth, setup):
    payload = body(setup, (setup["tea"], 1))
    payload["items"][0]["unit_price"] = 1
    payload["subtotal"] = 1
    order = place(client, auth, factory.user(), payload).json()
    assert Decimal(order["total"]) == Decimal("150")


def test_sold_out_message_and_rollback(client, factory, auth, setup, db):
    plov = setup["plov"]
    plov.available_portions = 5
    db.commit()
    r = place(client, auth, factory.user(), body(setup, (setup["tea"], 1), (plov, 6)))
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "sold_out"
    assert error["message"] == "Плов: осталось 5 порций"
    assert error["details"] == {"menu_item_id": plov.id, "available": 5}
    db.expire_all()
    # Nothing was taken: the tea deduction rolled back with the rest.
    assert db.get(MenuItem, setup["tea"].id).available_portions == 50
    assert db.get(PickupSlot, setup["slot"].id).booked_count == 0
    assert db.scalar(select(func.count(Order.id))) == 0


def test_portions_word():
    words = [orders.portions_word(n) for n in (0, 1, 2, 5, 11, 21, 22, 112)]
    assert words == ["порций", "порция", "порции", "порций", "порций", "порция", "порции", "порций"]


def test_severe_allergy_blocks_mild_needs_ack(client, factory, auth, freeze, db):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY)
    nuts, milk = factory.allergen("nuts"), factory.allergen("milk")
    cake = factory.menu_item(canteen, factory.dish(name_ru="Медовик", allergens=[nuts]), day=DAY)
    latte = factory.menu_item(canteen, factory.dish(name_ru="Латте", allergens=[milk]), day=DAY)
    user = factory.user()
    factory.user_allergen(user, nuts, AllergySeverity.severe)
    factory.user_allergen(user, milk, AllergySeverity.mild)
    ctx = {"canteen": canteen, "slot": slot}

    r = place(client, auth, user, body(ctx, (cake, 1), ack=True))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "allergy_blocked"
    assert "Медовик" in r.json()["error"]["message"]

    r = place(client, auth, user, body(ctx, (latte, 1)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "allergy_ack_required"
    assert r.json()["error"]["details"]["allergens"] == ["milk"]

    r = place(client, auth, user, body(ctx, (latte, 1), ack=True))
    assert r.status_code == 201
    assert r.json()["allergy_warning_ack"] is True
    # The kitchen-facing order never carries allergy details.
    assert "allergens" not in r.json()


def test_unverified_email_cannot_order(client, factory, auth, setup):
    r = place(client, auth, factory.user(verified=False), body(setup, (setup["tea"], 1)))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "email_not_verified"


def test_staff_cannot_order(client, factory, auth, setup):
    cook = factory.user(UserRole.cook, canteen=setup["canteen"])
    assert place(client, auth, cook, body(setup, (setup["tea"], 1))).status_code == 403


def test_slot_overlapping_lesson_is_rejected(client, factory, auth, setup):
    group = factory.group()
    factory.lesson(group, 1, "11:30", "12:50")
    student = factory.user(group=group)
    r = place(client, auth, student, body(setup, (setup["tea"], 1)))
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "by_schedule"


def test_slot_after_cutoff_is_rejected(client, factory, auth, setup, freeze):
    freeze("2026-10-12 11:50")
    r = place(client, auth, factory.user(), body(setup, (setup["tea"], 1)))
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "too_late"


def test_menu_item_of_other_day_is_rejected(client, factory, auth, setup):
    other = factory.menu_item(setup["canteen"], day=DAY + timedelta(days=1))
    r = place(client, auth, factory.user(), body(setup, (other, 1)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "menu_item_unavailable"


def test_order_limits(client, factory, auth, setup):
    user = factory.user()
    r = place(client, auth, user, body(setup, (setup["tea"], 11)))
    assert r.status_code == 422
    r = place(client, auth, user, {**body(setup), "items": []})
    assert r.status_code == 422
    r = place(client, auth, user, body(setup, (setup["tea"], 6), (setup["tea"], 5)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "quantity_too_large"


def test_order_rate_limit(client, factory, auth, setup, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "orders_per_minute", 2)
    user = factory.user()
    for _ in range(2):
        assert place(client, auth, user, body(setup, (setup["tea"], 1))).status_code == 201
    assert place(client, auth, user, body(setup, (setup["tea"], 1))).status_code == 429


# ---- concurrency (SPEC 13) ------------------------------------------------


@pytest.fixture(scope="module")
def ThreadSession():
    """A pool big enough for every thread to hold its own connection at the barrier."""
    from sqlalchemy.orm import sessionmaker

    from app.db import engine

    big = create_engine(
        engine.url,
        pool_size=60,
        max_overflow=0,
        connect_args={"options": "-c timezone=Asia/Almaty"},
    )
    yield sessionmaker(bind=big, autoflush=False, expire_on_commit=False)
    big.dispose()


def _parallel_orders(Session, user_ids, payload: OrderCreate) -> tuple[list, list]:
    ok, errors = [], []
    barrier = threading.Barrier(len(user_ids))
    lock = threading.Lock()

    def worker(uid: int) -> None:
        with Session() as session:
            user = session.get(User, uid)
            barrier.wait()
            try:
                result = orders.create_order(session, user, payload)
                with lock:
                    ok.append(result)
            except DomainError as exc:
                with lock:
                    errors.append(exc.code)

    threads = [threading.Thread(target=worker, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return ok, errors


def test_fifty_parallel_orders_do_not_overfill_slot(factory, setup, db, ThreadSession):
    users = [factory.user(UserRole.teacher).id for _ in range(50)]
    payload = OrderCreate(
        canteen_id=setup["canteen"].id,
        pickup_slot_id=setup["slot"].id,
        items=[OrderItemIn(menu_item_id=setup["tea"].id, quantity=1)],
    )
    tea = setup["tea"]
    tea.available_portions = tea.planned_portions = 100
    db.commit()

    ok, errors = _parallel_orders(ThreadSession, users, payload)
    assert len(ok) == 30
    assert len(errors) == 20 and set(errors) <= {"slot_full", "slot_unavailable"}
    db.expire_all()
    assert db.get(PickupSlot, setup["slot"].id).booked_count == 30
    # Portions taken by the failed orders were rolled back.
    assert db.get(MenuItem, tea.id).available_portions == 70
    numbers = [o.order_number for o in ok]
    assert len(set(numbers)) == 30
    assert sorted(numbers) == [f"A-{i:03d}" for i in range(1, 31)]


def test_last_portion_goes_to_one_of_two(factory, setup, db, ThreadSession):
    plov = setup["plov"]
    plov.available_portions = 1
    db.commit()
    users = [factory.user(UserRole.teacher).id for _ in range(2)]
    payload = OrderCreate(
        canteen_id=setup["canteen"].id,
        pickup_slot_id=setup["slot"].id,
        items=[OrderItemIn(menu_item_id=plov.id, quantity=1)],
    )
    ok, errors = _parallel_orders(ThreadSession, users, payload)
    assert len(ok) == 1
    assert errors == ["sold_out"]
    db.expire_all()
    assert db.get(MenuItem, plov.id).available_portions == 0
    assert db.get(PickupSlot, setup["slot"].id).booked_count == 1


def test_order_numbers_unique_in_parallel_across_slots(factory, setup, db, ThreadSession):
    second = factory.slot(setup["canteen"], day=DAY, starts="12:10")
    users = [factory.user(UserRole.teacher).id for _ in range(20)]
    tea = setup["tea"].id
    results: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(users))

    def worker(i: int, uid: int) -> None:
        slot_id = setup["slot"].id if i % 2 else second.id
        with ThreadSession() as session:
            user = session.get(User, uid)
            barrier.wait()
            out = orders.create_order(
                session,
                user,
                OrderCreate(
                    canteen_id=setup["canteen"].id,
                    pickup_slot_id=slot_id,
                    items=[OrderItemIn(menu_item_id=tea, quantity=1)],
                ),
            )
            with lock:
                results.append(out.order_number)

    threads = [threading.Thread(target=worker, args=(i, u)) for i, u in enumerate(users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 20 and len(set(results)) == 20


def test_next_order_number_per_day_and_prefix(db, factory):
    canteen = factory.canteen()
    assert orders.next_order_number(db, canteen.id, DAY, "A") == "A-001"
    assert orders.next_order_number(db, canteen.id, DAY, "A") == "A-002"
    assert orders.next_order_number(db, canteen.id, DAY, "K") == "K-001"
    assert orders.next_order_number(db, canteen.id, DAY + timedelta(days=1), "A") == "A-001"
    db.commit()


# ---- statuses (SPEC 7.6) --------------------------------------------------


ALL_ACTORS = list(Actor)


@pytest.mark.parametrize("current", list(OrderStatus))
@pytest.mark.parametrize("target", list(OrderStatus))
def test_forbidden_transitions_raise(current, target, db, factory, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY)
    user = factory.user()
    order = Order(
        order_number="A-001",
        user_id=user.id,
        canteen_id=canteen.id,
        service_date=DAY,
        pickup_slot_id=slot.id,
        channel="mobile_app",
        status=current,
    )
    db.add(order)
    db.commit()
    allowed = TRANSITIONS.get((current, target), frozenset())
    for actor in ALL_ACTORS:
        if actor in allowed:
            continue
        with pytest.raises(ConflictError) as exc:
            change_status(db, order, target, actor, user.id)
        assert exc.value.code == "invalid_transition"
    db.rollback()


def test_allowed_transition_records_who(db, factory, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    cook = factory.user(UserRole.cook, canteen=canteen)
    order = Order(
        order_number="A-001",
        user_id=factory.user().id,
        canteen_id=canteen.id,
        service_date=DAY,
        pickup_slot_id=factory.slot(canteen, day=DAY).id,
        channel="mobile_app",
        status=OrderStatus.paid,
    )
    db.add(order)
    db.commit()
    change_status(db, order, OrderStatus.cooking, Actor.kitchen, cook.id)
    db.commit()
    last = db.scalar(select(OrderStatusHistory).order_by(OrderStatusHistory.id.desc()).limit(1))
    assert last.to_status == OrderStatus.cooking and last.changed_by == cook.id


def test_stale_status_is_rejected(db, factory, freeze):
    """Compare-and-set: a second change from the same old status fails."""
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    order = Order(
        order_number="A-001",
        user_id=factory.user().id,
        canteen_id=canteen.id,
        service_date=DAY,
        pickup_slot_id=factory.slot(canteen, day=DAY).id,
        channel="mobile_app",
        status=OrderStatus.paid,
    )
    db.add(order)
    db.commit()
    with SessionLocal() as other:
        stale = other.get(Order, order.id)
        change_status(db, order, OrderStatus.cooking, Actor.kitchen)
        db.commit()
        with pytest.raises(ConflictError) as exc:
            change_status(other, stale, OrderStatus.cancelled, Actor.customer)
        assert exc.value.code == "status_changed"


def test_is_allowed_table():
    assert order_status.is_allowed(OrderStatus.paid, OrderStatus.cooking, Actor.kitchen)
    assert not order_status.is_allowed(OrderStatus.paid, OrderStatus.cooking, Actor.customer)
    assert not order_status.is_allowed(OrderStatus.picked_up, OrderStatus.paid, Actor.system)


# ---- cancel / repeat / history -------------------------------------------


def test_cancel_returns_portions_and_place(client, factory, auth, setup, db):
    user = factory.user()
    order = place(client, auth, user, body(setup, (setup["plov"], 3))).json()
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(user))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    db.expire_all()
    assert db.get(MenuItem, setup["plov"].id).available_portions == 20
    assert db.get(PickupSlot, setup["slot"].id).booked_count == 0
    payment = db.scalar(select(Payment).where(Payment.order_id == order["id"]))
    assert payment.status == PaymentStatus.failed
    # A second cancel is a forbidden transition and returns nothing twice.
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(user))
    assert r.status_code == 409
    db.expire_all()
    assert db.get(MenuItem, setup["plov"].id).available_portions == 20


def _mark_paid(db, order_id: int) -> None:
    order = db.get(Order, order_id)
    change_status(db, order, OrderStatus.paid, Actor.system)
    payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
    payment.status = PaymentStatus.succeeded
    db.commit()


def test_paid_order_cancel_window(client, factory, auth, setup, db, freeze):
    user = factory.user()
    order = place(client, auth, user, body(setup, (setup["tea"], 1))).json()
    _mark_paid(db, order["id"])

    freeze("2026-10-12 11:31")  # 29 minutes before the 12:00 slot
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "cancel_too_late"

    freeze("2026-10-12 11:29")
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(user)).json()
    assert detail["can_cancel"] is True
    assert datetime.fromisoformat(detail["cancel_until"]) == clock.combine_local(DAY, time(11, 30))
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(user))
    assert r.status_code == 200
    db.expire_all()
    payment = db.scalar(select(Payment).where(Payment.order_id == order["id"]))
    assert payment.status == PaymentStatus.refunded


def test_cooking_order_cannot_be_cancelled(client, factory, auth, setup, db):
    user = factory.user()
    order = place(client, auth, user, body(setup, (setup["tea"], 1))).json()
    _mark_paid(db, order["id"])
    change_status(db, db.get(Order, order["id"]), OrderStatus.cooking, Actor.kitchen)
    db.commit()
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_transition"


def test_foreign_order_is_not_found(client, factory, auth, setup):
    owner = factory.user()
    order = place(client, auth, owner, body(setup, (setup["tea"], 1))).json()
    stranger = factory.user()
    for method, path in (
        ("get", f"/api/v1/orders/{order['id']}"),
        ("post", f"/api/v1/orders/{order['id']}/cancel"),
        ("post", f"/api/v1/orders/{order['id']}/repeat"),
    ):
        assert getattr(client, method)(path, headers=auth(stranger)).status_code == 404


def test_my_orders_newest_first(client, factory, auth, setup):
    user = factory.user()
    first = place(client, auth, user, body(setup, (setup["tea"], 1))).json()
    second = place(client, auth, user, body(setup, (setup["plov"], 1))).json()
    place(client, auth, factory.user(), body(setup, (setup["tea"], 1)))
    listed = client.get("/api/v1/orders", headers=auth(user)).json()
    assert listed["total"] == 2
    assert [o["id"] for o in listed["items"]] == [second["id"], first["id"]]


def test_repeat_builds_cart_from_available_items(client, factory, auth, setup, db):
    user = factory.user()
    order = place(client, auth, user, body(setup, (setup["plov"], 2), (setup["tea"], 1))).json()
    plov = db.get(MenuItem, setup["plov"].id)
    plov.available_portions = 0
    db.commit()
    r = client.post(f"/api/v1/orders/{order['id']}/repeat", headers=auth(user))
    assert r.status_code == 200
    cart = r.json()
    assert [i["name_ru"] for i in cart["items"]] == ["Чай"]
    assert cart["skipped"] == [{"dish_id": plov.dish_id, "name_ru": "Плов", "reason": "sold_out"}]


def test_no_show_warning(client, factory, auth, setup, db):
    user = factory.user()
    canteen, slot = setup["canteen"], setup["slot"]
    for n in range(3):
        db.add(
            Order(
                order_number=f"A-9{n}",
                user_id=user.id,
                canteen_id=canteen.id,
                service_date=DAY,
                pickup_slot_id=slot.id,
                channel="mobile_app",
                status=OrderStatus.no_show,
            )
        )
    db.commit()
    order = place(client, auth, user, body(setup, (setup["tea"], 1))).json()
    assert order["no_show_warning"] is True
