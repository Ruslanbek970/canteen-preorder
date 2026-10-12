from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import ValidationError
from app.models import (
    AllergySeverity,
    MenuItem,
    Order,
    OrderChannel,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentStatus,
    UserRole,
    WasteReason,
    WasteRecord,
)
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import orders, payments, pickup
from app.services.order_status import Actor, change_status

DAY = date(2026, 10, 12)


@pytest.fixture
def p(factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    cashier = factory.user(UserRole.cashier, canteen=canteen)
    slot = factory.slot(canteen, day=DAY, starts="12:00", minutes=10)
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", price=1500), day=DAY, portions=20
    )
    tea = factory.menu_item(canteen, factory.dish(name_ru="Чай", price=150), day=DAY, portions=20)
    return {"canteen": canteen, "cashier": cashier, "slot": slot, "plov": plov, "tea": tea}


def make_order(db, factory, p, status=OrderStatus.ready, user=None):
    user = user or factory.user(UserRole.teacher, full_name="Аружан Сапарова")
    out = orders.create_order(
        db,
        user,
        OrderCreate(
            canteen_id=p["canteen"].id,
            pickup_slot_id=p["slot"].id,
            items=[OrderItemIn(menu_item_id=p["plov"].id, quantity=2)],
            allergy_warning_ack=True,
        ),
    )
    payments.settle(db, out.payment_id, True, f"t{out.id}")
    order = db.get(Order, out.id)
    path = [OrderStatus.cooking, OrderStatus.ready]
    for step in path[: path.index(status) + 1] if status in path else []:
        fields = {"pickup_shelf": 4} if step == OrderStatus.ready else {}
        change_status(db, order, step, Actor.kitchen, **fields)
        db.commit()
    return order


def test_normalize_number():
    assert pickup.normalize_number("a7") == "A-007"
    assert pickup.normalize_number(" A-007 ") == "A-007"
    assert pickup.normalize_number("12") == "A-012"
    assert pickup.normalize_number("k-3") == "K-003"
    with pytest.raises(ValidationError):
        pickup.normalize_number("hello")


def test_scan_and_confirm(client, auth, db, factory, p):
    order = make_order(db, factory, p)
    h = auth(p["cashier"])
    found = client.get(f"/api/v1/pickup/scan/{order.qr_token}", headers=h).json()
    assert found["order_number"] == "A-001" and found["pickup_shelf"] == 4
    assert found["status"] == "ready" and found["customer_name"] == "Аружан Сапарова"
    assert found["items"] == [{"menu_item_id": p["plov"].id, "name": "Плов", "quantity": 2}]

    r = client.post(f"/api/v1/pickup/orders/{order.id}/confirm", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "picked_up"
    assert r.json()["picked_up_at"] is not None
    who = db.scalar(
        select(OrderStatusHistory.changed_by).where(
            OrderStatusHistory.order_id == order.id,
            OrderStatusHistory.to_status == OrderStatus.picked_up,
        )
    )
    assert who == p["cashier"].id
    # Handing it over twice is refused.
    r = client.post(f"/api/v1/pickup/orders/{order.id}/confirm", headers=h)
    assert r.status_code == 409


def test_by_number_today_only(client, auth, db, factory, p, freeze):
    order = make_order(db, factory, p)
    h = auth(p["cashier"])
    assert client.get("/api/v1/pickup/by-number/a1", headers=h).json()["id"] == order.id
    assert client.get("/api/v1/pickup/by-number/A-002", headers=h).status_code == 404
    assert client.get("/api/v1/pickup/by-number/xyz", headers=h).status_code == 422
    freeze("2026-10-13 10:00")
    assert client.get("/api/v1/pickup/by-number/A-001", headers=h).status_code == 404


def test_cooking_order_cannot_be_handed_over(client, auth, db, factory, p):
    order = make_order(db, factory, p, status=OrderStatus.cooking)
    r = client.post(f"/api/v1/pickup/orders/{order.id}/confirm", headers=auth(p["cashier"]))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "order_not_ready"
    assert r.json()["error"]["details"]["status"] == "cooking"


def test_pickup_shows_only_allergy_line(client, auth, db, factory, p):
    student = factory.user()
    nuts = factory.allergen("nuts")
    nuts.name_ru = "Орехи"
    factory.user_allergen(student, nuts, AllergySeverity.severe)
    order = make_order(db, factory, p, user=student)
    found = client.get(f"/api/v1/pickup/scan/{order.qr_token}", headers=auth(p["cashier"])).json()
    assert found["allergy_flag"] == "АЛЛЕРГИЯ: ОРЕХИ"
    assert "severe" not in str(found)


def test_other_canteen_and_roles(client, auth, db, factory, p):
    order = make_order(db, factory, p)
    other_cashier = factory.user(UserRole.cashier)
    assert (
        client.get(f"/api/v1/pickup/scan/{order.qr_token}", headers=auth(other_cashier)).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/pickup/orders/{order.id}/confirm", headers=auth(other_cashier)
        ).status_code
        == 404
    )
    for role in (UserRole.student, UserRole.cook, UserRole.admin):
        h = auth(factory.user(role))
        assert client.get(f"/api/v1/pickup/scan/{order.qr_token}", headers=h).status_code == 403
        assert client.post("/api/v1/pos/sales", json={}, headers=h).status_code in (403, 422)
    assert (
        client.get("/api/v1/pickup/scan/not-a-uuid", headers=auth(p["cashier"])).status_code == 404
    )


def test_pos_sale(client, auth, db, p):
    h = auth(p["cashier"])
    body = {
        "items": [
            {"menu_item_id": p["plov"].id, "quantity": 1},
            {"menu_item_id": p["tea"].id, "quantity": 2},
        ],
        "method": "cash",
    }
    r = client.post("/api/v1/pos/sales", json=body, headers=h)
    assert r.status_code == 201, r.text
    receipt = r.json()
    assert receipt["order_number"] == "K-001"
    assert Decimal(receipt["total"]) == Decimal("1800")
    assert receipt["fiscal_receipt_number"].startswith("MOCK-")
    order = db.get(Order, receipt["order_id"])
    assert order.channel == OrderChannel.cashier and order.user_id is None
    assert order.status == OrderStatus.picked_up and order.picked_up_at is not None
    payment = db.scalar(select(Payment).where(Payment.order_id == order.id))
    assert payment.status == PaymentStatus.succeeded and payment.method.value == "cash"
    db.expire_all()
    assert db.get(MenuItem, p["tea"].id).available_portions == 18
    second = client.post(
        "/api/v1/pos/sales",
        json={"items": [{"menu_item_id": p["tea"].id, "quantity": 1}], "method": "kaspi_qr"},
        headers=h,
    ).json()
    assert second["order_number"] == "K-002"


def test_pos_sold_out_and_wrong_items(client, auth, db, factory, p):
    h = auth(p["cashier"])
    plov = db.get(MenuItem, p["plov"].id)
    plov.available_portions = 1
    db.commit()
    r = client.post(
        "/api/v1/pos/sales",
        json={"items": [{"menu_item_id": plov.id, "quantity": 2}], "method": "cash"},
        headers=h,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"
    other = factory.menu_item(factory.canteen(), day=DAY)
    r = client.post(
        "/api/v1/pos/sales",
        json={"items": [{"menu_item_id": other.id, "quantity": 1}], "method": "cash"},
        headers=h,
    )
    assert r.status_code == 422
    r = client.post(
        "/api/v1/pos/sales",
        json={"items": [{"menu_item_id": plov.id, "quantity": 1}], "method": "bank_card"},
        headers=h,
    )
    assert r.status_code == 422


def test_mark_no_show_after_30_minutes_and_idempotent(db, factory, p, freeze):
    ready = make_order(db, factory, p)
    cooking = make_order(db, factory, p, status=OrderStatus.cooking)
    freeze("2026-10-12 12:39")  # slot ended 12:10, only 29 minutes ago
    assert pickup.mark_no_show(db) == 0
    freeze("2026-10-12 12:41")
    assert pickup.mark_no_show(db) == 1
    assert pickup.mark_no_show(db) == 0
    db.expire_all()
    assert db.get(Order, ready.id).status == OrderStatus.no_show
    assert db.get(Order, cooking.id).status == OrderStatus.cooking
    waste = db.scalars(select(WasteRecord)).all()
    assert [(w.portions, w.reason, w.order_id) for w in waste] == [
        (2, WasteReason.uncollected_order, ready.id)
    ]


def test_no_show_job(db, factory, p, freeze):
    from worker import jobs

    make_order(db, factory, p)
    freeze("2026-10-12 13:00")
    assert jobs.mark_no_show() == 1
