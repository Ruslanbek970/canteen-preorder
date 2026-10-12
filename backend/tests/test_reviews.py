from datetime import date

import pytest
from sqlalchemy import update

from app.models import Order, OrderStatus, UserRole
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import orders, payments
from app.services.order_status import Actor, change_status
from app.utils import time as clock

DAY = date(2026, 10, 12)


@pytest.fixture
def r(factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:00")
    plov = factory.menu_item(canteen, factory.dish(name_ru="Плов"), day=DAY, portions=50)
    return {"canteen": canteen, "slot": slot, "plov": plov}


def picked_up(db, factory, r, user=None, status=OrderStatus.picked_up):
    user = user or factory.user()
    out = orders.create_order(
        db,
        user,
        OrderCreate(
            canteen_id=r["canteen"].id,
            pickup_slot_id=r["slot"].id,
            items=[OrderItemIn(menu_item_id=r["plov"].id, quantity=1)],
        ),
    )
    payments.settle(db, out.payment_id, True, f"rv-{out.id}")
    order = db.get(Order, out.id)
    steps = [OrderStatus.cooking, OrderStatus.ready, OrderStatus.picked_up]
    for step in steps[: steps.index(status) + 1] if status in steps else []:
        actor = Actor.pickup if step == OrderStatus.picked_up else Actor.kitchen
        change_status(db, order, step, actor)
        db.commit()
    return user, order


def test_review_after_pickup_once(client, auth, db, factory, r):
    user, order = picked_up(db, factory, r)
    h = auth(user)
    item_id = order.items[0].id
    detail = client.get(f"/api/v1/orders/{order.id}", headers=h).json()
    assert detail["review_until"] is not None and detail["items"][0]["my_rating"] is None

    resp = client.post(
        f"/api/v1/order-items/{item_id}/review",
        json={"rating": 5, "comment": " Вкусно "},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["comment"] == "Вкусно"
    detail = client.get(f"/api/v1/orders/{order.id}", headers=h).json()
    assert detail["items"][0]["my_rating"] == 5

    again = client.post(f"/api/v1/order-items/{item_id}/review", json={"rating": 1}, headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_reviewed"


def test_review_rules(client, auth, db, factory, r, freeze):
    user, cooking = picked_up(db, factory, r, status=OrderStatus.cooking)
    h = auth(user)
    resp = client.post(
        f"/api/v1/order-items/{cooking.items[0].id}/review", json={"rating": 4}, headers=h
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "order_not_picked_up"

    _, done = picked_up(db, factory, r, user=user)
    # The trigger stamps picked_up_at with the real now(); pin it to the frozen clock.
    db.execute(update(Order).where(Order.id == done.id).values(picked_up_at=clock.now_utc()))
    db.commit()
    item = done.items[0].id
    assert (
        client.post(f"/api/v1/order-items/{item}/review", json={"rating": 6}, headers=h).status_code
        == 422
    )
    stranger = auth(factory.user())
    assert (
        client.post(
            f"/api/v1/order-items/{item}/review", json={"rating": 4}, headers=stranger
        ).status_code
        == 404
    )
    cook = auth(factory.user(UserRole.cook))
    assert (
        client.post(
            f"/api/v1/order-items/{item}/review", json={"rating": 4}, headers=cook
        ).status_code
        == 403
    )

    freeze("2026-10-14 11:00")  # more than 48 hours after pickup
    resp = client.post(f"/api/v1/order-items/{item}/review", json={"rating": 4}, headers=h)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "review_window_closed"
    assert client.get(f"/api/v1/orders/{done.id}", headers=h).json()["review_until"] is None


def test_rating_shows_in_menu_after_three_reviews(client, auth, db, factory, r):
    dish_id = r["plov"].dish_id
    for rating in (5, 4):
        user, order = picked_up(db, factory, r)
        client.post(
            f"/api/v1/order-items/{order.items[0].id}/review",
            json={"rating": rating},
            headers=auth(user),
        )
    card = client.get(f"/api/v1/dishes/{dish_id}").json()
    assert card["rating"] is None and card["rating_count"] == 2
    user, order = picked_up(db, factory, r)
    client.post(
        f"/api/v1/order-items/{order.items[0].id}/review", json={"rating": 3}, headers=auth(user)
    )
    card = client.get(f"/api/v1/dishes/{dish_id}").json()
    assert card["rating"] == 4.0 and card["rating_count"] == 3
