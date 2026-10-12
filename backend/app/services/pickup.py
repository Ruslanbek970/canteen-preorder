"""Pickup by QR or number, POS sales, no-shows (SPEC 7.6, 7.9)."""

import re
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import get_settings
from app.db import set_current_user
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    MenuItem,
    Order,
    OrderChannel,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    PickupSlot,
    User,
    WasteReason,
    WasteRecord,
)
from app.payments import get_provider
from app.schemas.kitchen import KitchenLine
from app.schemas.pickup import PickupOrder, PosReceipt, PosSale
from app.services import allergens as allergy
from app.services import pricing
from app.services.order_status import Actor, change_status
from app.services.orders import next_order_number, take_portions
from app.utils import time as clock

NUMBER = re.compile(r"^([AK])?-?\s*(\d{1,4})$")


def normalize_number(raw: str) -> str:
    """`a7`, `A007`, `7` -> `A-007`; `k-12` -> `K-012`."""
    match = NUMBER.match(raw.strip().upper())
    if match is None:
        raise ValidationError("invalid_order_number", "Неверный номер заказа")
    prefix = match.group(1) or "A"
    return f"{prefix}-{int(match.group(2)):03d}"


def _query(canteen_id: int):
    return (
        select(Order)
        .options(
            selectinload(Order.items).joinedload(OrderItem.menu_item).joinedload(MenuItem.dish),
            joinedload(Order.pickup_slot),
        )
        .where(Order.canteen_id == canteen_id)
    )


def to_pickup(db: Session, order: Order) -> PickupOrder:
    slot = order.pickup_slot
    customer = db.get(User, order.user_id) if order.user_id else None
    return PickupOrder(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        pickup_shelf=order.pickup_shelf,
        starts_at=slot.starts_at if slot else None,
        ends_at=slot.ends_at if slot else None,
        customer_name=customer.full_name if customer else None,
        items=[
            KitchenLine(
                menu_item_id=i.menu_item_id, name=i.menu_item.dish.name_ru, quantity=i.quantity
            )
            for i in order.items
        ],
        total=order.total,
        allergy_flag=allergy.sticker_flag(db, order.user_id),
        picked_up_at=order.picked_up_at,
    )


def by_qr(db: Session, canteen_id: int, qr_token: str) -> PickupOrder:
    try:
        token = uuid.UUID(qr_token)
    except ValueError as exc:
        raise NotFoundError("order", "Заказ не найден") from exc
    order = db.scalar(_query(canteen_id).where(Order.qr_token == token))
    if order is None:
        raise NotFoundError("order", "Заказ не найден")
    return to_pickup(db, order)


def by_number(db: Session, canteen_id: int, raw: str) -> PickupOrder:
    number = normalize_number(raw)
    order = db.scalar(
        _query(canteen_id).where(
            Order.order_number == number, Order.service_date == clock.today_local()
        )
    )
    if order is None:
        raise NotFoundError("order", f"Заказ {number} за сегодня не найден")
    return to_pickup(db, order)


def confirm(db: Session, staff: User, canteen_id: int, order_id: int) -> PickupOrder:
    """`ready -> picked_up`; anything else is a clear 409 the screen shows in large type."""
    order = db.scalar(_query(canteen_id).where(Order.id == order_id).with_for_update(of=Order))
    if order is None:
        raise NotFoundError("order", "Заказ не найден")
    if order.status != OrderStatus.ready:
        raise ConflictError(
            "order_not_ready",
            "Заказ ещё не готов"
            if order.status in (OrderStatus.paid, OrderStatus.cooking)
            else "Этот заказ нельзя выдать",
            {"status": order.status},
        )
    change_status(db, order, OrderStatus.picked_up, Actor.pickup, staff.id)
    db.commit()
    return to_pickup(db, db.scalar(_query(canteen_id).where(Order.id == order_id)))


def pos_sale(db: Session, staff: User, canteen_id: int, data: PosSale) -> PosReceipt:
    """A sale at the till: no customer, no slot, paid and handed over at once (SPEC 7.9).
    The order is inserted already `picked_up`, so it never enters the transition table."""
    quantities: dict[int, int] = defaultdict(int)
    for line in data.items:
        quantities[line.menu_item_id] += line.quantity
    today = clock.today_local()
    menu_items = list(
        db.scalars(
            select(MenuItem)
            .options(joinedload(MenuItem.dish))
            .where(
                MenuItem.id.in_(quantities),
                MenuItem.canteen_id == canteen_id,
                MenuItem.menu_date == today,
            )
            .order_by(MenuItem.id)
        )
    )
    missing = sorted(set(quantities) - {mi.id for mi in menu_items})
    if missing:
        raise ValidationError(
            "menu_item_unavailable", "Блюда нет в меню на сегодня", {"menu_item_ids": missing}
        )
    try:
        for mi in menu_items:
            take_portions(db, mi, quantities[mi.id])
        number = next_order_number(db, canteen_id, today, "K")
        now = clock.now_utc()
        promos = pricing.item_promotions(db, quantities, now)
        order = Order(
            order_number=number,
            canteen_id=canteen_id,
            service_date=today,
            channel=OrderChannel.cashier,
            status=OrderStatus.picked_up,
            paid_at=now,
            picked_up_at=now,
        )
        subtotal = discount_total = Decimal("0")
        for mi in menu_items:
            qty = quantities[mi.id]
            promo = promos.get(mi.id)
            discount = pricing.line_discount(
                mi.price, qty, promo.discount_percent if promo else None
            )
            order.items.append(
                OrderItem(
                    menu_item_id=mi.id,
                    quantity=qty,
                    unit_price=mi.price,
                    promotion_id=promo.id if promo else None,
                    discount_amount=discount,
                )
            )
            subtotal += mi.price * qty
            discount_total += discount
        order.subtotal, order.discount_total = subtotal, discount_total
        set_current_user(db, staff.id)
        db.add(order)
        db.flush()
        payment = None
        if subtotal - discount_total > 0:
            payment = Payment(
                order_id=order.id,
                method=data.method,
                amount=subtotal - discount_total,
                status=PaymentStatus.succeeded,
                completed_at=now,
            )
            db.add(payment)
            db.flush()
            payment.fiscal_receipt_number = get_provider().fiscal_receipt_number(payment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return PosReceipt(
        order_id=order.id,
        order_number=number,
        method=data.method,
        subtotal=subtotal,
        discount_total=discount_total,
        total=subtotal - discount_total,
        fiscal_receipt_number=payment.fiscal_receipt_number if payment else None,
        items=[
            KitchenLine(menu_item_id=mi.id, name=mi.dish.name_ru, quantity=quantities[mi.id])
            for mi in menu_items
        ],
    )


def mark_no_show(db: Session) -> int:
    """Worker, every 5 minutes: `ready` orders 30 minutes after the slot ended become `no_show`
    and their portions are written off as `uncollected_order`. Idempotent."""
    settings = get_settings()
    deadline = clock.now_utc() - timedelta(minutes=settings.no_show_after_minutes)
    slot_end = func.timezone(settings.tz, PickupSlot.slot_date + PickupSlot.ends_at)
    ids = db.scalars(
        select(Order.id)
        .join(PickupSlot, PickupSlot.id == Order.pickup_slot_id)
        .where(Order.status == OrderStatus.ready, slot_end < deadline)
        .order_by(Order.id)
    ).all()
    marked = 0
    for order_id in ids:
        order = db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.status == OrderStatus.ready)
            .with_for_update(skip_locked=True)
        )
        if order is None:
            db.rollback()
            continue
        change_status(db, order, OrderStatus.no_show, Actor.system)
        for item in order.items:
            db.add(
                WasteRecord(
                    menu_item_id=item.menu_item_id,
                    portions=item.quantity,
                    reason=WasteReason.uncollected_order,
                    order_id=order.id,
                )
            )
        db.commit()
        marked += 1
    return marked
