"""Kitchen board, prep summary, statuses, shelves, labels, waste (SPEC 7.8)."""

from collections import defaultdict
from datetime import date, time

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.errors import ConflictError, NotFoundError
from app.models import (
    Canteen,
    Dish,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PickupSlot,
    User,
    WasteReason,
    WasteRecord,
)
from app.schemas.kitchen import (
    BoardSlot,
    CloseDayResult,
    KitchenBoard,
    KitchenLine,
    KitchenOrder,
    Label,
    PrepLine,
    PrepSlot,
    PrepSummary,
    SlotStartResult,
    WasteIn,
    WasteOut,
)
from app.services import allergens as allergy
from app.services.order_status import Actor, change_status
from app.services.orders import next_order_number
from app.utils import time as clock

ACTIVE = (OrderStatus.paid, OrderStatus.cooking, OrderStatus.ready)
STORABLE_HOURS = 24


def _lines(order: Order) -> list[KitchenLine]:
    return [
        KitchenLine(menu_item_id=i.menu_item_id, name=i.menu_item.dish.name_ru, quantity=i.quantity)
        for i in order.items
    ]


def _orders_query(canteen_id: int):
    return (
        select(Order)
        .options(
            selectinload(Order.items).joinedload(OrderItem.menu_item).joinedload(MenuItem.dish),
            joinedload(Order.pickup_slot),
        )
        .where(Order.canteen_id == canteen_id)
    )


def to_kitchen_order(db: Session, order: Order, flags: dict[int, str | None]) -> KitchenOrder:
    if order.user_id is not None and order.user_id not in flags:
        flags[order.user_id] = allergy.sticker_flag(db, order.user_id)
    return KitchenOrder(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        channel=order.channel,
        pickup_slot_id=order.pickup_slot_id,
        pickup_shelf=order.pickup_shelf,
        paid_at=order.paid_at,
        items=_lines(order),
        allergy_flag=flags.get(order.user_id) if order.user_id is not None else None,
    )


def board(db: Session, canteen_id: int, day: date | None) -> KitchenBoard:
    day = day or clock.today_local()
    orders = db.scalars(
        _orders_query(canteen_id)
        .where(Order.service_date == day, Order.status.in_(ACTIVE))
        .order_by(Order.id)
    ).all()
    by_slot: dict[int | None, list[Order]] = defaultdict(list)
    for o in orders:
        by_slot[o.pickup_slot_id].append(o)
    flags: dict[int, str | None] = {}
    result = []

    def slot_key(group: list[Order]) -> tuple[bool, time]:
        slot = group[0].pickup_slot
        return (slot is None, slot.starts_at if slot else time.min)

    ordered = sorted(by_slot.items(), key=lambda kv: slot_key(kv[1]))
    for slot_id, slot_orders in ordered:
        slot = slot_orders[0].pickup_slot
        result.append(
            BoardSlot(
                slot_id=slot_id,
                starts_at=slot.starts_at if slot else None,
                ends_at=slot.ends_at if slot else None,
                orders=[to_kitchen_order(db, o, flags) for o in slot_orders],
            )
        )
    counts = {s.value: 0 for s in ACTIVE}
    for o in orders:
        counts[o.status.value] += 1
    return KitchenBoard(canteen_id=canteen_id, date=day, slots=result, counts=counts)


def prep_summary(db: Session, canteen_id: int, limit: int = 3) -> PrepSummary:
    """«к 12:00 собрать: Плов × 14»: paid and cooking orders of the next slots."""
    now = clock.now_local()
    today = now.date()
    rows = db.execute(
        select(PickupSlot, Dish.name_ru, OrderItem.quantity, Order.id)
        .join(Order, Order.pickup_slot_id == PickupSlot.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Dish, Dish.id == MenuItem.dish_id)
        .where(
            PickupSlot.canteen_id == canteen_id,
            PickupSlot.slot_date == today,
            PickupSlot.ends_at > now.time(),
            Order.status.in_((OrderStatus.paid, OrderStatus.cooking)),
        )
        .order_by(PickupSlot.starts_at)
    ).all()
    slots: dict[int, PickupSlot] = {}
    totals: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    order_ids: dict[int, set[int]] = defaultdict(set)
    for slot, name, qty, order_id in rows:
        slots[slot.id] = slot
        totals[slot.id][name] += qty
        order_ids[slot.id].add(order_id)
    result = []
    for slot_id in list(slots)[:limit]:
        slot = slots[slot_id]
        items = sorted(totals[slot_id].items(), key=lambda kv: (-kv[1], kv[0]))
        result.append(
            PrepSlot(
                slot_id=slot_id,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                orders=len(order_ids[slot_id]),
                items=[PrepLine(name=n, quantity=q) for n, q in items],
            )
        )
    return PrepSummary(canteen_id=canteen_id, date=today, slots=result)


def _get_order(db: Session, canteen_id: int, order_id: int, lock: bool = False) -> Order:
    stmt = _orders_query(canteen_id).where(Order.id == order_id)
    if lock:
        stmt = stmt.with_for_update(of=Order)
    order = db.scalar(stmt)
    if order is None:
        raise NotFoundError("order", "Заказ не найден")
    return order


def next_shelf(db: Session, canteen: Canteen, day: date) -> int:
    """Round robin 1..pickup_shelves_count, atomic through the daily counter (prefix S)."""
    value = int(next_order_number(db, canteen.id, day, "S").split("-")[1])
    return (value - 1) % max(canteen.pickup_shelves_count, 1) + 1


def set_status(
    db: Session, staff: User, canteen_id: int, order_id: int, target: OrderStatus
) -> KitchenOrder:
    order = _get_order(db, canteen_id, order_id, lock=True)
    fields = {}
    if target == OrderStatus.ready and order.status == OrderStatus.cooking:
        canteen = db.get(Canteen, canteen_id)
        assert canteen is not None
        fields["pickup_shelf"] = next_shelf(db, canteen, order.service_date)
    try:
        change_status(db, order, target, Actor.kitchen, staff.id, **fields)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return to_kitchen_order(db, _get_order(db, canteen_id, order_id), {})


def start_slot(db: Session, staff: User, canteen_id: int, slot_id: int) -> SlotStartResult:
    """«Взять в работу весь слот»: every paid order of the slot goes to cooking."""
    slot = db.scalar(
        select(PickupSlot).where(PickupSlot.id == slot_id, PickupSlot.canteen_id == canteen_id)
    )
    if slot is None:
        raise NotFoundError("slot", "Слот не найден")
    orders = db.scalars(
        select(Order)
        .where(Order.pickup_slot_id == slot_id, Order.status == OrderStatus.paid)
        .order_by(Order.id)
        .with_for_update(skip_locked=True)
    ).all()
    started = []
    for order in orders:
        change_status(db, order, OrderStatus.cooking, Actor.kitchen, staff.id)
        started.append(order.id)
    db.commit()
    return SlotStartResult(slot_id=slot_id, order_ids=started)


def label(db: Session, canteen_id: int, order_id: int) -> Label:
    order = _get_order(db, canteen_id, order_id)
    canteen = db.get(Canteen, canteen_id)
    slot = order.pickup_slot
    return Label(
        order_id=order.id,
        order_number=order.order_number,
        canteen_name=canteen.name if canteen else "",
        service_date=order.service_date,
        starts_at=slot.starts_at if slot else None,
        ends_at=slot.ends_at if slot else None,
        items=_lines(order),
        allergy_flag=allergy.sticker_flag(db, order.user_id),
    )


def _waste_out(record: WasteRecord, dish_name: str) -> WasteOut:
    return WasteOut(
        id=record.id,
        menu_item_id=record.menu_item_id,
        dish_name=dish_name,
        portions=record.portions,
        reason=record.reason,
        recorded_at=record.recorded_at,
    )


def record_waste(db: Session, staff: User, canteen_id: int, data: WasteIn) -> WasteOut:
    """Manual write-off: takes the portions atomically, never below zero."""
    mi = db.scalar(
        select(MenuItem)
        .options(joinedload(MenuItem.dish))
        .where(MenuItem.id == data.menu_item_id, MenuItem.canteen_id == canteen_id)
    )
    if mi is None:
        raise NotFoundError("menu_item", "Блюдо не найдено в меню")
    taken = db.execute(
        update(MenuItem)
        .where(MenuItem.id == mi.id, MenuItem.available_portions >= data.portions)
        .values(available_portions=MenuItem.available_portions - data.portions)
        .returning(MenuItem.id)
    ).first()
    if taken is None:
        db.rollback()
        raise ConflictError(
            "waste_above_available",
            "Нельзя списать больше, чем осталось",
            {"available": mi.available_portions},
        )
    record = WasteRecord(
        menu_item_id=mi.id, portions=data.portions, reason=data.reason, recorded_by=staff.id
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _waste_out(record, mi.dish.name_ru)


def close_day(db: Session, staff: User, canteen_id: int, day: date | None = None) -> CloseDayResult:
    """«Закрыть день»: leftovers that do not keep until tomorrow are written off as expired.
    Idempotent: the written-off portions are taken, so a second run finds nothing."""
    day = day or clock.today_local()
    items = db.scalars(
        select(MenuItem)
        .options(joinedload(MenuItem.dish))
        .where(
            MenuItem.canteen_id == canteen_id,
            MenuItem.menu_date == day,
            MenuItem.available_portions > 0,
        )
        .order_by(MenuItem.id)
        .with_for_update(of=MenuItem)
    ).all()
    written, kept = [], []
    for mi in items:
        if mi.dish.shelf_life_hours >= STORABLE_HOURS:
            kept.append(PrepLine(name=mi.dish.name_ru, quantity=mi.available_portions))
            continue
        record = WasteRecord(
            menu_item_id=mi.id,
            portions=mi.available_portions,
            reason=WasteReason.expired,
            recorded_by=staff.id,
        )
        mi.available_portions = 0
        db.add(record)
        written.append((record, mi.dish.name_ru))
    db.commit()
    for record, _ in written:
        db.refresh(record)
    return CloseDayResult(
        date=day, written_off=[_waste_out(r, name) for r, name in written], kept=kept
    )


def waste_list(db: Session, canteen_id: int, day: date | None = None) -> list[WasteOut]:
    day = day or clock.today_local()
    rows = db.execute(
        select(WasteRecord, Dish.name_ru)
        .join(MenuItem, MenuItem.id == WasteRecord.menu_item_id)
        .join(Dish, Dish.id == MenuItem.dish_id)
        .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date == day)
        .order_by(WasteRecord.id.desc())
    ).all()
    return [_waste_out(r, name) for r, name in rows]
