import json
from datetime import date

import pytest
from sqlalchemy import select

from app.models import (
    AllergySeverity,
    MenuItem,
    Order,
    OrderStatus,
    OrderStatusHistory,
    UserRole,
    WasteReason,
    WasteRecord,
)
from app.schemas.orders import OrderCreate, OrderItemIn
from app.security import create_access_token
from app.services import orders, payments

DAY = date(2026, 10, 12)


@pytest.fixture
def k(factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen(pickup_shelves_count=2)
    cook = factory.user(UserRole.cook, canteen=canteen)
    s12 = factory.slot(canteen, day=DAY, starts="12:00")
    s13 = factory.slot(canteen, day=DAY, starts="13:00")
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", shelf_life_hours=12), day=DAY, portions=50
    )
    tea = factory.menu_item(
        canteen, factory.dish(name_ru="Чай", shelf_life_hours=48), day=DAY, portions=50
    )
    return {"canteen": canteen, "cook": cook, "s12": s12, "s13": s13, "plov": plov, "tea": tea}


def paid_order(db, factory, k, slot, lines, user=None):
    user = user or factory.user(UserRole.teacher)
    out = orders.create_order(
        db,
        user,
        OrderCreate(
            canteen_id=k["canteen"].id,
            pickup_slot_id=slot.id,
            items=[OrderItemIn(menu_item_id=mi.id, quantity=q) for mi, q in lines],
            allergy_warning_ack=True,
        ),
    )
    payments.settle(db, out.payment_id, True, f"t-{out.id}")
    return out


def test_board_groups_by_slot_and_status(client, auth, db, factory, k):
    a = paid_order(db, factory, k, k["s13"], [(k["plov"], 1)])
    b = paid_order(db, factory, k, k["s12"], [(k["tea"], 2)])
    # Unpaid orders are not on the board.
    orders.create_order(
        db,
        factory.user(UserRole.teacher),
        OrderCreate(
            canteen_id=k["canteen"].id,
            pickup_slot_id=k["s12"].id,
            items=[OrderItemIn(menu_item_id=k["tea"].id, quantity=1)],
        ),
    )
    board = client.get("/api/v1/kitchen/board", headers=auth(k["cook"])).json()
    assert [s["starts_at"] for s in board["slots"]] == ["12:00:00", "13:00:00"]
    assert [o["id"] for o in board["slots"][0]["orders"]] == [b.id]
    assert board["slots"][1]["orders"][0]["items"] == [
        {"menu_item_id": k["plov"].id, "name": "Плов", "quantity": 1}
    ]
    assert board["counts"] == {"paid": 2, "cooking": 0, "ready": 0}
    assert a.id


def test_kitchen_sees_only_allergy_line(client, auth, db, factory, k):
    student = factory.user()
    nuts, milk = factory.allergen("nuts"), factory.allergen("milk")
    nuts.name_ru, milk.name_ru = "Орехи", "Молоко"
    factory.user_allergen(student, nuts, AllergySeverity.severe)
    factory.user_allergen(student, milk, AllergySeverity.mild)
    order = paid_order(db, factory, k, k["s12"], [(k["tea"], 1)], user=student)
    board = client.get("/api/v1/kitchen/board", headers=auth(k["cook"])).json()
    card = board["slots"][0]["orders"][0]
    assert card["allergy_flag"] == "АЛЛЕРГИЯ: МОЛОКО, ОРЕХИ"
    text = json.dumps(board, ensure_ascii=False)
    assert "severe" not in text and "mild" not in text and "nuts" not in text
    label = client.get(f"/api/v1/kitchen/orders/{order.id}/label", headers=auth(k["cook"])).json()
    assert label["allergy_flag"] == "АЛЛЕРГИЯ: МОЛОКО, ОРЕХИ"
    assert label["starts_at"] == "12:00:00" and label["order_number"] == order.order_number


def test_prep_summary(client, auth, db, factory, k, freeze):
    paid_order(db, factory, k, k["s12"], [(k["plov"], 2), (k["tea"], 1)])
    paid_order(db, factory, k, k["s12"], [(k["plov"], 3)])
    paid_order(db, factory, k, k["s13"], [(k["tea"], 4)])
    summary = client.get("/api/v1/kitchen/prep-summary", headers=auth(k["cook"])).json()
    first = summary["slots"][0]
    assert first["starts_at"] == "12:00:00" and first["orders"] == 2
    assert first["items"] == [{"name": "Плов", "quantity": 5}, {"name": "Чай", "quantity": 1}]
    assert summary["slots"][1]["items"] == [{"name": "Чай", "quantity": 4}]
    # Slots that are over drop out of the summary.
    freeze("2026-10-12 12:30")
    later = client.get("/api/v1/kitchen/prep-summary", headers=auth(k["cook"])).json()
    assert [s["starts_at"] for s in later["slots"]] == ["13:00:00"]


def test_status_flow_assigns_shelves_round_robin(client, auth, db, factory, k):
    h = auth(k["cook"])
    ids = [paid_order(db, factory, k, k["s12"], [(k["tea"], 1)]).id for _ in range(3)]
    shelves = []
    for order_id in ids:
        r = client.post(
            f"/api/v1/kitchen/orders/{order_id}/status", json={"status": "cooking"}, headers=h
        )
        assert r.status_code == 200 and r.json()["status"] == "cooking"
        r = client.post(
            f"/api/v1/kitchen/orders/{order_id}/status", json={"status": "ready"}, headers=h
        )
        shelves.append(r.json()["pickup_shelf"])
    assert shelves == [1, 2, 1]  # pickup_shelves_count = 2
    history = db.scalars(
        select(OrderStatusHistory.changed_by).where(
            OrderStatusHistory.order_id == ids[0],
            OrderStatusHistory.to_status == OrderStatus.ready,
        )
    ).all()
    assert history == [k["cook"].id]


def test_kitchen_cannot_skip_or_go_back(client, auth, db, factory, k):
    h = auth(k["cook"])
    order = paid_order(db, factory, k, k["s12"], [(k["tea"], 1)])
    r = client.post(
        f"/api/v1/kitchen/orders/{order.id}/status", json={"status": "ready"}, headers=h
    )
    assert r.status_code == 409
    r = client.post(
        f"/api/v1/kitchen/orders/{order.id}/status", json={"status": "picked_up"}, headers=h
    )
    assert r.status_code == 422


def test_start_whole_slot(client, auth, db, factory, k):
    a = paid_order(db, factory, k, k["s12"], [(k["tea"], 1)])
    b = paid_order(db, factory, k, k["s12"], [(k["plov"], 1)])
    other = paid_order(db, factory, k, k["s13"], [(k["tea"], 1)])
    r = client.post(f"/api/v1/kitchen/slots/{k['s12'].id}/start", headers=auth(k["cook"]))
    assert r.json() == {"slot_id": k["s12"].id, "order_ids": [a.id, b.id]}
    db.expire_all()
    assert db.get(Order, a.id).status == OrderStatus.cooking
    assert db.get(Order, other.id).status == OrderStatus.paid
    # Again: nothing left to start.
    r = client.post(f"/api/v1/kitchen/slots/{k['s12'].id}/start", headers=auth(k["cook"]))
    assert r.json()["order_ids"] == []


def test_foreign_canteen_is_invisible(client, auth, db, factory, k):
    order = paid_order(db, factory, k, k["s12"], [(k["tea"], 1)])
    stranger = factory.user(UserRole.cook)  # another canteen
    h = auth(stranger)
    assert client.get("/api/v1/kitchen/board", headers=h).json()["slots"] == []
    r = client.post(
        f"/api/v1/kitchen/orders/{order.id}/status", json={"status": "cooking"}, headers=h
    )
    assert r.status_code == 404
    assert client.get(f"/api/v1/kitchen/orders/{order.id}/label", headers=h).status_code == 404
    assert client.post(f"/api/v1/kitchen/slots/{k['s12'].id}/start", headers=h).status_code == 404


@pytest.mark.parametrize(
    "role", [UserRole.student, UserRole.teacher, UserRole.cashier, UserRole.admin]
)
def test_other_roles_get_403(client, auth, factory, role):
    h = auth(factory.user(role))
    assert client.get("/api/v1/kitchen/board", headers=h).status_code == 403
    assert client.post("/api/v1/kitchen/close-day", headers=h).status_code == 403


def test_manager_uses_kitchen(client, auth, db, factory, k):
    manager = factory.user(UserRole.canteen_manager, canteen=k["canteen"])
    paid_order(db, factory, k, k["s12"], [(k["tea"], 1)])
    board = client.get("/api/v1/kitchen/board", headers=auth(manager)).json()
    assert board["counts"]["paid"] == 1


def test_close_day_writes_off_perishable_only_and_is_idempotent(client, auth, db, factory, k):
    paid_order(db, factory, k, k["s12"], [(k["plov"], 5)])
    h = auth(k["cook"])
    r = client.post("/api/v1/kitchen/close-day", headers=h).json()
    assert [(w["dish_name"], w["portions"], w["reason"]) for w in r["written_off"]] == [
        ("Плов", 45, "expired")
    ]
    assert r["kept"] == [{"name": "Чай", "quantity": 50}]
    db.expire_all()
    assert db.get(MenuItem, k["plov"].id).available_portions == 0
    assert db.get(MenuItem, k["tea"].id).available_portions == 50
    again = client.post("/api/v1/kitchen/close-day", headers=h).json()
    assert again["written_off"] == []
    records = db.scalars(select(WasteRecord)).all()
    assert len(records) == 1 and records[0].recorded_by == k["cook"].id


def test_manual_waste(client, auth, db, k):
    h = auth(k["cook"])
    body = {"menu_item_id": k["tea"].id, "portions": 3, "reason": "damaged"}
    r = client.post("/api/v1/kitchen/waste", json=body, headers=h)
    assert r.status_code == 201 and r.json()["dish_name"] == "Чай"
    db.expire_all()
    assert db.get(MenuItem, k["tea"].id).available_portions == 47
    too_many = {**body, "portions": 48}
    r = client.post("/api/v1/kitchen/waste", json=too_many, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "waste_above_available"
    r = client.post(
        "/api/v1/kitchen/waste", json={**body, "reason": WasteReason.uncollected_order}, headers=h
    )
    assert r.status_code == 422
    listed = client.get("/api/v1/kitchen/waste", headers=h).json()
    assert [w["portions"] for w in listed] == [3]


def test_paid_order_reaches_kitchen_socket(client, auth, db, factory, k):
    """SPEC phase 5 'done when': an order paid on the phone appears on the kitchen screen."""
    student = factory.user()
    out = orders.create_order(
        db,
        student,
        OrderCreate(
            canteen_id=k["canteen"].id,
            pickup_slot_id=k["s12"].id,
            items=[OrderItemIn(menu_item_id=k["tea"].id, quantity=1)],
        ),
    )
    token = create_access_token(k["cook"])
    with client.websocket_connect(f"/ws/kitchen/{k['canteen'].id}?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"
        client.post(f"/api/v1/payments/mock/{out.payment_id}/confirm", headers=auth(student))
        message = ws.receive_json()
        assert message["type"] == "order.paid" and message["data"]["order_id"] == out.id
