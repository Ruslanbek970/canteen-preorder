"""Customer orders: creation in one transaction, cancel, repeat, history (SPEC 5.3, 7.5, 7.6)."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app import ratelimit
from app.config import get_settings
from app.db import set_current_user
from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import (
    Canteen,
    DailyCounter,
    MenuItem,
    Order,
    OrderChannel,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PickupSlot,
    User,
)
from app.schemas.orders import (
    CartLine,
    OrderCreate,
    OrderItemOut,
    OrderList,
    OrderOut,
    OrderSlotOut,
    RepeatResponse,
    SkippedLine,
)
from app.services import allergens as allergy
from app.services import menu as menu_service
from app.services import pricing, slots, users
from app.services.order_status import Actor, change_status
from app.utils import time as clock

NO_SHOW_WARNING_THRESHOLD = 3


def next_order_number(db: Session, canteen_id: int, service_date: date, prefix: str) -> str:
    """Daily counter per canteen and prefix: `A-007` (SPEC 5.3)."""
    stmt = insert(DailyCounter).values(
        canteen_id=canteen_id, service_date=service_date, prefix=prefix, last_value=1
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["canteen_id", "service_date", "prefix"],
        set_={"last_value": DailyCounter.last_value + 1},
    ).returning(DailyCounter.last_value)
    value = db.execute(stmt).scalar_one()
    return f"{prefix}-{value:03d}"


def portions_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "порция"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "порции"
    return "порций"


def take_portions(db: Session, menu_item: MenuItem, quantity: int) -> None:
    """Atomic: `UPDATE ... WHERE available_portions >= :qty RETURNING` (SPEC 5.3)."""
    taken = db.execute(
        update(MenuItem)
        .where(MenuItem.id == menu_item.id, MenuItem.available_portions >= quantity)
        .values(available_portions=MenuItem.available_portions - quantity)
        .returning(MenuItem.id)
    ).first()
    if taken is None:
        left = db.scalar(select(MenuItem.available_portions).where(MenuItem.id == menu_item.id))
        raise ConflictError(
            "sold_out",
            f"{menu_item.dish.name_ru}: осталось {left or 0} {portions_word(left or 0)}",
            {"menu_item_id": menu_item.id, "available": left or 0},
        )


def return_portions(db: Session, items: list[OrderItem]) -> None:
    for item in sorted(items, key=lambda i: i.menu_item_id):
        db.execute(
            update(MenuItem)
            .where(MenuItem.id == item.menu_item_id)
            .values(
                available_portions=func.least(
                    MenuItem.available_portions + item.quantity, MenuItem.planned_portions
                )
            )
        )


def _merge_lines(data: OrderCreate) -> dict[int, int]:
    quantities: dict[int, int] = defaultdict(int)
    for line in data.items:
        quantities[line.menu_item_id] += line.quantity
    too_many = [mid for mid, q in quantities.items() if q > 10]
    if too_many:
        raise ValidationError(
            "quantity_too_large", "Не больше 10 штук одного блюда", {"menu_item_ids": too_many}
        )
    return dict(quantities)


def _check_allergies(db: Session, user: User, menu_items: list[MenuItem], ack: bool) -> None:
    """Repeated on the server even if the client already checked (SPEC 7.3)."""
    mine = allergy.user_allergies(db, user)
    if not mine:
        return
    by_dish = allergy.dish_allergens(db, [mi.dish_id for mi in menu_items])
    blocked, warned = [], []
    for mi in menu_items:
        result = allergy.assess(by_dish.get(mi.dish_id, []), mine)
        if result.unsafe:
            blocked.append((mi, result.severe))
        elif result.warning:
            warned.append((mi, result.other))
    if blocked:
        mi, found = blocked[0]
        raise ValidationError(
            "allergy_blocked",
            f"«{mi.dish.name_ru}» нельзя заказать: {', '.join(a.name_ru for a in found)}",
            {"menu_item_ids": [m.id for m, _ in blocked]},
        )
    if warned and not ack:
        raise ValidationError(
            "allergy_ack_required",
            "В заказе есть блюда с вашими аллергенами, подтвердите заказ",
            {
                "menu_item_ids": [m.id for m, _ in warned],
                "allergens": sorted({a.code for _, found in warned for a in found}),
            },
        )


def create_order(db: Session, user: User, data: OrderCreate) -> OrderOut:
    settings = get_settings()
    if user.email_verified_at is None:
        raise ForbiddenError("email_not_verified", "Подтвердите e-mail, чтобы делать заказы")
    ratelimit.hit(f"orders:{user.id}", settings.orders_per_minute)

    canteen = menu_service.get_canteen(db, data.canteen_id)
    quantities = _merge_lines(data)

    slot = db.scalar(
        select(PickupSlot).where(
            PickupSlot.id == data.pickup_slot_id, PickupSlot.canteen_id == canteen.id
        )
    )
    if slot is None:
        raise NotFoundError("slot", "Слот не найден")
    check = slots.check_slot(db, slot, canteen, user)
    if check.ok and slot.slot_date not in menu_service.available_dates():
        check = slots.SlotCheck(False, "date_unavailable")
    if not check.ok:
        raise ConflictError(
            "slot_unavailable", "Этот слот недоступен, выберите другой", {"reason": check.reason}
        )

    menu_items = list(
        db.scalars(
            select(MenuItem)
            .options(joinedload(MenuItem.dish))
            .where(MenuItem.id.in_(quantities))
            .order_by(MenuItem.id)
        )
    )
    found = {mi.id for mi in menu_items}
    usable = {
        mi.id
        for mi in menu_items
        if mi.canteen_id == canteen.id and mi.menu_date == slot.slot_date and mi.dish.is_active
    }
    wrong = [mid for mid in quantities if mid not in usable]
    if wrong:
        raise ValidationError(
            "menu_item_unavailable", "Блюдо недоступно на этот день", {"menu_item_ids": wrong}
        )

    _check_allergies(db, user, menu_items, data.allergy_warning_ack)

    # One transaction: portions (ascending id, no deadlocks) -> slot -> number -> rows.
    try:
        for mi in menu_items:
            take_portions(db, mi, quantities[mi.id])
        if not slots.book(db, slot.id):
            raise ConflictError(
                "slot_full", "В этом слоте закончились места, выберите другой", {"reason": "full"}
            )
        number = next_order_number(db, canteen.id, slot.slot_date, "A")

        now = clock.now_utc()
        item_promos = pricing.item_promotions(db, found, now)
        slot_promo = pricing.slot_promotions(db, [slot.id], now).get(slot.id)
        order = Order(
            order_number=number,
            user_id=user.id,
            canteen_id=canteen.id,
            service_date=slot.slot_date,
            pickup_slot_id=slot.id,
            channel=OrderChannel.mobile_app,
            status=OrderStatus.pending_payment,
            allergy_warning_ack=data.allergy_warning_ack,
        )
        subtotal = Decimal("0")
        discount_total = Decimal("0")
        for mi in menu_items:
            qty = quantities[mi.id]
            promo = pricing.best_promotion(item_promos.get(mi.id), slot_promo)
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
        order.subtotal = subtotal
        order.discount_total = discount_total

        set_current_user(db, user.id)
        db.add(order)
        db.flush()
        amount = subtotal - discount_total
        payment = None
        if amount > 0:
            payment = Payment(order_id=order.id, method=PaymentMethod.kaspi_qr, amount=amount)
            db.add(payment)
        db.commit()
    except Exception:
        db.rollback()
        raise

    out = order_out(db, get_order_for(db, user, order.id))
    out.no_show_warning = users.no_show_count(db, user.id) >= NO_SHOW_WARNING_THRESHOLD
    return out


def cancel_deadline(order: Order) -> datetime | None:
    if order.pickup_slot is None:
        return None
    minutes = get_settings().paid_cancel_before_slot_minutes
    return slots.slot_start(order.pickup_slot) - timedelta(minutes=minutes)


def can_cancel(order: Order) -> bool:
    if order.status == OrderStatus.pending_payment:
        return True
    if order.status == OrderStatus.paid:
        deadline = cancel_deadline(order)
        return deadline is not None and clock.now_local() < deadline
    return False


def cancel_order(db: Session, user: User, order_id: int) -> OrderOut:
    """Returns portions and the slot place in the same transaction (SPEC 5.3)."""
    order = get_order_for(db, user, order_id)
    if order.status == OrderStatus.paid and not can_cancel(order):
        raise ConflictError(
            "cancel_too_late",
            "Оплаченный заказ можно отменить не позже чем за "
            f"{get_settings().paid_cancel_before_slot_minutes} минут до слота",
        )
    try:
        was_paid = order.status == OrderStatus.paid
        change_status(db, order, OrderStatus.cancelled, Actor.customer, user.id)
        release_resources(db, order)
        if was_paid:
            refund_payments(db, order)
        else:
            fail_pending_payments(db, order)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return order_out(db, get_order_for(db, user, order_id))


def release_resources(db: Session, order: Order) -> None:
    return_portions(db, list(order.items))
    if order.pickup_slot_id is not None:
        slots.release(db, order.pickup_slot_id)


def refund_payments(db: Session, order: Order) -> None:
    """Mock refund; phase 4 routes it through the PaymentProvider."""
    db.execute(
        update(Payment)
        .where(Payment.order_id == order.id, Payment.status == PaymentStatus.succeeded)
        .values(status=PaymentStatus.refunded, completed_at=clock.now_utc())
    )


def fail_pending_payments(db: Session, order: Order) -> None:
    db.execute(
        update(Payment)
        .where(Payment.order_id == order.id, Payment.status == PaymentStatus.pending)
        .values(status=PaymentStatus.failed, completed_at=clock.now_utc())
    )


def get_order_for(db: Session, user: User, order_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).joinedload(OrderItem.menu_item).joinedload(MenuItem.dish),
            joinedload(Order.pickup_slot),
        )
        .where(Order.id == order_id)
        .execution_options(populate_existing=True)
    )
    # Someone else's order looks exactly like a missing one.
    if order is None or order.user_id != user.id:
        raise NotFoundError("order", "Заказ не найден")
    return order


def order_out(db: Session, order: Order) -> OrderOut:
    canteen = db.get(Canteen, order.canteen_id)
    payment_id = db.scalar(
        select(Payment.id).where(Payment.order_id == order.id).order_by(Payment.id.desc()).limit(1)
    )
    slot = order.pickup_slot
    return OrderOut(
        id=order.id,
        order_number=order.order_number,
        canteen_id=order.canteen_id,
        canteen_name=canteen.name if canteen else "",
        service_date=order.service_date,
        channel=order.channel,
        status=order.status,
        pickup_slot=OrderSlotOut(
            id=slot.id, slot_date=slot.slot_date, starts_at=slot.starts_at, ends_at=slot.ends_at
        )
        if slot
        else None,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        total=order.total,
        qr_token=order.qr_token,
        pickup_shelf=order.pickup_shelf,
        allergy_warning_ack=order.allergy_warning_ack,
        created_at=order.created_at,
        paid_at=order.paid_at,
        ready_at=order.ready_at,
        picked_up_at=order.picked_up_at,
        items=[
            OrderItemOut(
                id=i.id,
                menu_item_id=i.menu_item_id,
                dish_id=i.menu_item.dish_id,
                name_ru=i.menu_item.dish.name_ru,
                name_kk=i.menu_item.dish.name_kk,
                quantity=i.quantity,
                unit_price=i.unit_price,
                discount_amount=i.discount_amount,
                line_total=i.unit_price * i.quantity - i.discount_amount,
                promotion_id=i.promotion_id,
            )
            for i in order.items
        ],
        payment_id=payment_id,
        payment_url=None,
        can_cancel=can_cancel(order),
        cancel_until=cancel_deadline(order) if order.status == OrderStatus.paid else None,
    )


def list_orders(db: Session, user: User, limit: int, offset: int) -> OrderList:
    total = db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id)) or 0
    orders = db.scalars(
        select(Order)
        .options(
            selectinload(Order.items).joinedload(OrderItem.menu_item).joinedload(MenuItem.dish),
            joinedload(Order.pickup_slot),
        )
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return OrderList(items=[order_out(db, o) for o in orders], total=total)


def repeat_order(db: Session, user: User, order_id: int, day: date | None) -> RepeatResponse:
    """A cart from a past order: only dishes that are on today's menu and safe for the user."""
    order = get_order_for(db, user, order_id)
    days = menu_service.available_dates()
    day = day if day in days else days[0]
    dish_ids = [i.menu_item.dish_id for i in order.items]
    current = {
        mi.dish_id: mi
        for mi in db.scalars(
            select(MenuItem)
            .options(joinedload(MenuItem.dish))
            .where(
                MenuItem.canteen_id == order.canteen_id,
                MenuItem.menu_date == day,
                MenuItem.dish_id.in_(dish_ids),
            )
        )
    }
    mine = allergy.user_allergies(db, user)
    by_dish = allergy.dish_allergens(db, dish_ids)
    promos = pricing.item_promotions(db, [mi.id for mi in current.values()], clock.now_utc())
    lines: list[CartLine] = []
    skipped: list[SkippedLine] = []
    for item in order.items:
        dish = item.menu_item.dish
        mi = current.get(dish.id)
        if mi is None or not dish.is_active:
            skipped.append(SkippedLine(dish_id=dish.id, name_ru=dish.name_ru, reason="not_on_menu"))
        elif mi.available_portions < 1:
            skipped.append(SkippedLine(dish_id=dish.id, name_ru=dish.name_ru, reason="sold_out"))
        elif (check := allergy.assess(by_dish.get(dish.id, []), mine)).unsafe:
            skipped.append(SkippedLine(dish_id=dish.id, name_ru=dish.name_ru, reason="allergy"))
        else:
            promo = promos.get(mi.id)
            lines.append(
                CartLine(
                    menu_item_id=mi.id,
                    dish_id=dish.id,
                    name_ru=dish.name_ru,
                    name_kk=dish.name_kk,
                    price=mi.price,
                    discount_percent=promo.discount_percent if promo else None,
                    quantity=min(item.quantity, mi.available_portions),
                    available_portions=mi.available_portions,
                    warning_for_me=check.warning,
                )
            )
    return RepeatResponse(canteen_id=order.canteen_id, date=day, items=lines, skipped=skipped)
