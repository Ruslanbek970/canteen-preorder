"""The only place where an order's status changes (SPEC 7.6)."""

from enum import StrEnum
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import set_current_user
from app.errors import ConflictError
from app.models import Order, OrderStatus
from app.ws import events


class Actor(StrEnum):
    system = "system"
    customer = "customer"
    kitchen = "kitchen"
    pickup = "pickup"


S = OrderStatus

# (from, to) -> who may perform the transition. Everything else is a 409.
TRANSITIONS: dict[tuple[OrderStatus, OrderStatus], frozenset[Actor]] = {
    (S.pending_payment, S.paid): frozenset({Actor.system}),
    (S.pending_payment, S.cancelled): frozenset({Actor.customer, Actor.system}),
    (S.paid, S.cancelled): frozenset({Actor.customer}),
    (S.paid, S.cooking): frozenset({Actor.kitchen}),
    (S.cooking, S.ready): frozenset({Actor.kitchen}),
    (S.ready, S.picked_up): frozenset({Actor.pickup}),
    (S.ready, S.no_show): frozenset({Actor.system}),
}


def is_allowed(current: OrderStatus, target: OrderStatus, actor: Actor) -> bool:
    return actor in TRANSITIONS.get((current, target), frozenset())


def change_status(
    db: Session,
    order: Order,
    target: OrderStatus,
    actor: Actor,
    user_id: int | None = None,
    **fields: Any,
) -> Order:
    """Compare-and-set the status inside the caller's transaction (the caller commits).

    `SET LOCAL app.current_user_id` lets the history trigger record who did it.
    """
    current = order.status
    if not is_allowed(current, target, actor):
        raise ConflictError(
            "invalid_transition",
            f"Нельзя перевести заказ из «{current}» в «{target}»",
            {"from": current, "to": target},
        )
    set_current_user(db, user_id)
    changed = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == current)
        .values(status=target, **fields)
        .returning(Order.id)
    ).first()
    if changed is None:
        raise ConflictError(
            "status_changed", "Статус заказа уже изменился, обновите страницу", {"to": target}
        )
    db.refresh(order)
    kind = {S.paid: "order.paid", S.cancelled: "order.cancelled"}.get(
        target, "order.status_changed"
    )
    events.order_event(db, kind, order)
    return order
