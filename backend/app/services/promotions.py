"""Discounts (SPEC 7.10): leftovers proposed by the system, off-peak slots, approval by the manager.
Prices themselves are applied in `pricing` (the biggest active discount per line wins)."""

from datetime import datetime, time, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Canteen,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PickupSlot,
    Promotion,
    PromotionStatus,
    PromotionType,
    User,
    UserRole,
)
from app.notifications import service as notifications
from app.schemas.promotions import OffPeakCreate, PromotionOut
from app.utils import time as clock

LEFTOVER_FROM = time(13, 30)
LEFTOVER_MIN_SHARE = 0.25  # more than a quarter of the plan is still there
LEFTOVER_HOURS_LEFT = 2  # and it spoils in less than two hours
LEFTOVER_PERCENT = 30
OFF_PEAK_LOAD = 0.3  # a slot less than 30% full
OFF_PEAK_LEAD = timedelta(hours=1)  # an hour before it starts
OFF_PEAK_PERCENT = 20
RECENT_BUYERS_DAYS = 30
SOLD = (OrderStatus.paid, OrderStatus.cooking, OrderStatus.ready, OrderStatus.picked_up)


def _expires_at(mi: MenuItem) -> datetime | None:
    if mi.cooked_at is None:
        return None
    return mi.cooked_at + timedelta(hours=mi.dish.shelf_life_hours)


def to_out(promo: Promotion) -> PromotionOut:
    mi, slot = promo.menu_item, promo.pickup_slot
    return PromotionOut(
        id=promo.id,
        type=promo.type,
        status=promo.status,
        discount_percent=promo.discount_percent,
        valid_from=promo.valid_from,
        valid_to=promo.valid_to,
        created_by_system=promo.created_by_system,
        created_at=promo.created_at,
        menu_item_id=promo.menu_item_id,
        dish_name=mi.dish.name_ru if mi else None,
        available_portions=mi.available_portions if mi else None,
        planned_portions=mi.planned_portions if mi else None,
        pickup_slot_id=promo.pickup_slot_id,
        slot_date=slot.slot_date if slot else None,
        slot_starts_at=slot.starts_at if slot else None,
        slot_ends_at=slot.ends_at if slot else None,
        slot_booked=slot.booked_count if slot else None,
        slot_capacity=slot.capacity if slot else None,
    )


def _query(canteen_id: int):
    return (
        select(Promotion)
        .options(
            joinedload(Promotion.menu_item).joinedload(MenuItem.dish),
            joinedload(Promotion.pickup_slot),
        )
        .outerjoin(MenuItem, MenuItem.id == Promotion.menu_item_id)
        .outerjoin(PickupSlot, PickupSlot.id == Promotion.pickup_slot_id)
        .where(or_(MenuItem.canteen_id == canteen_id, PickupSlot.canteen_id == canteen_id))
    )


def list_promotions(
    db: Session, canteen_id: int, status: PromotionStatus | None = None
) -> list[PromotionOut]:
    """Today's and future discounts, newest first."""
    start_of_day = clock.combine_local(clock.today_local(), time(0, 0))
    query = _query(canteen_id).where(Promotion.valid_to >= start_of_day)
    if status is not None:
        query = query.where(Promotion.status == status)
    rows = db.scalars(query.order_by(Promotion.created_at.desc(), Promotion.id.desc())).all()
    return [to_out(p) for p in rows]


def _get(db: Session, canteen_id: int, promotion_id: int) -> Promotion:
    promo = db.scalar(_query(canteen_id).where(Promotion.id == promotion_id))
    if promo is None:
        raise NotFoundError("promotion", "Скидка не найдена")
    return promo


def propose_leftover(db: Session) -> int:
    """Worker, every 30 minutes from 13:30: propose 30% off dishes that are left over and spoil
    soon. A dish gets at most one leftover proposal a day, so a rejection is final."""
    now = clock.now_utc()
    local = clock.now_local()
    if local.time() < LEFTOVER_FROM:
        return 0
    created = 0
    canteens = db.scalars(select(Canteen).where(Canteen.is_active)).all()
    for canteen in canteens:
        closes = clock.combine_local(local.date(), canteen.closes_at)
        if now >= closes:
            continue
        items = db.scalars(
            select(MenuItem)
            .options(joinedload(MenuItem.dish))
            .where(MenuItem.canteen_id == canteen.id, MenuItem.menu_date == local.date())
            .order_by(MenuItem.id)
        ).all()
        already = set(
            db.scalars(
                select(Promotion.menu_item_id).where(
                    Promotion.type == PromotionType.leftover,
                    Promotion.menu_item_id.in_([mi.id for mi in items]),
                )
            )
        )
        for mi in items:
            expires = _expires_at(mi)
            if mi.id in already or expires is None or not mi.planned_portions:
                continue
            if mi.available_portions <= mi.planned_portions * LEFTOVER_MIN_SHARE:
                continue
            if not now < expires <= now + timedelta(hours=LEFTOVER_HOURS_LEFT):
                continue
            db.add(
                Promotion(
                    type=PromotionType.leftover,
                    menu_item_id=mi.id,
                    discount_percent=LEFTOVER_PERCENT,
                    valid_from=now,
                    valid_to=min(expires, closes),
                    status=PromotionStatus.proposed,
                    created_by_system=True,
                )
            )
            created += 1
    db.commit()
    return created


def suggest_off_peak(db: Session) -> int:
    """Worker, every 30 minutes: propose 20% off slots that start within an hour and are less
    than 30% full. One proposal per slot."""
    now = clock.now_utc()
    today = clock.today_local()
    slots = db.scalars(
        select(PickupSlot)
        .join(Canteen, Canteen.id == PickupSlot.canteen_id)
        .outerjoin(
            Promotion,
            (Promotion.pickup_slot_id == PickupSlot.id)
            & (Promotion.type == PromotionType.off_peak),
        )
        .where(
            Canteen.is_active,
            PickupSlot.slot_date == today,
            ~PickupSlot.is_closed,
            Promotion.id.is_(None),
        )
        .order_by(PickupSlot.id)
    ).all()
    created = 0
    for slot in slots:
        start = clock.combine_local(slot.slot_date, slot.starts_at)
        if not now < start <= now + OFF_PEAK_LEAD:
            continue
        if slot.booked_count >= slot.capacity * OFF_PEAK_LOAD:
            continue
        db.add(
            Promotion(
                type=PromotionType.off_peak,
                pickup_slot_id=slot.id,
                discount_percent=OFF_PEAK_PERCENT,
                valid_from=now,
                valid_to=clock.combine_local(slot.slot_date, slot.ends_at),
                status=PromotionStatus.proposed,
                created_by_system=True,
            )
        )
        created += 1
    db.commit()
    return created


def create_off_peak(
    db: Session, manager: User, canteen_id: int, data: OffPeakCreate
) -> PromotionOut:
    slot = db.get(PickupSlot, data.pickup_slot_id)
    if slot is None or slot.canteen_id != canteen_id:
        raise NotFoundError("slot", "Слот не найден")
    now = clock.now_utc()
    ends = clock.combine_local(slot.slot_date, slot.ends_at)
    if ends <= now:
        raise ValidationError("slot_over", "Этот слот уже закончился")
    promo = Promotion(
        type=PromotionType.off_peak,
        pickup_slot_id=slot.id,
        discount_percent=data.discount_percent,
        valid_from=now,
        valid_to=ends,
        status=PromotionStatus.active,
        created_by_system=False,
        approved_by=manager.id,
    )
    db.add(promo)
    db.commit()
    return to_out(_get(db, canteen_id, promo.id))


def _decide(db: Session, manager: User, canteen_id: int, promotion_id: int, target) -> Promotion:
    promo = _get(db, canteen_id, promotion_id)
    if promo.status != PromotionStatus.proposed:
        raise ConflictError("promotion_not_proposed", "По этой скидке решение уже принято")
    if target == PromotionStatus.active and promo.valid_to <= clock.now_utc():
        raise ConflictError("promotion_expired", "Срок этой скидки уже прошёл")
    changed = db.execute(
        update(Promotion)
        .where(Promotion.id == promo.id, Promotion.status == PromotionStatus.proposed)
        .values(status=target, approved_by=manager.id)
        .returning(Promotion.id)
    ).first()
    if changed is None:
        raise ConflictError("promotion_not_proposed", "По этой скидке решение уже принято")
    db.refresh(promo)
    return promo


def approve(db: Session, manager: User, canteen_id: int, promotion_id: int) -> PromotionOut:
    promo = _decide(db, manager, canteen_id, promotion_id, PromotionStatus.active)
    if promo.type == PromotionType.leftover:
        broadcast_leftover(db, promo)
    db.commit()
    return to_out(_get(db, canteen_id, promo.id))


def reject(db: Session, manager: User, canteen_id: int, promotion_id: int) -> PromotionOut:
    promo = _decide(db, manager, canteen_id, promotion_id, PromotionStatus.rejected)
    db.commit()
    return to_out(_get(db, canteen_id, promo.id))


def recent_buyers(db: Session, dish_id: int, canteen_id: int) -> list[User]:
    since = clock.today_local() - timedelta(days=RECENT_BUYERS_DAYS)
    return list(
        db.scalars(
            select(User)
            .where(
                User.id.in_(
                    select(Order.user_id)
                    .join(OrderItem, OrderItem.order_id == Order.id)
                    .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
                    .where(
                        MenuItem.dish_id == dish_id,
                        Order.canteen_id == canteen_id,
                        Order.service_date >= since,
                        Order.status.in_(SOLD),
                    )
                ),
                User.is_active,
                User.role.in_([UserRole.student, UserRole.teacher]),
            )
            .order_by(User.id)
        )
    )


def broadcast_leftover(db: Session, promo: Promotion) -> int:
    """After approval: tell recent buyers of the dish who did not switch advertising off."""
    mi = promo.menu_item
    assert mi is not None
    canteen = db.get(Canteen, mi.canteen_id)
    until = promo.valid_to.astimezone(clock.local_tz()).strftime("%H:%M")
    sent = 0
    for user in recent_buyers(db, mi.dish_id, mi.canteen_id):
        dish = mi.dish.name_kk if user.preferred_language == "kk" and mi.dish.name_kk else None
        note = notifications.notify(
            db,
            user,
            "leftover_discount",
            promotion_id=promo.id,
            url="/menu",
            percent=promo.discount_percent,
            dish=dish or mi.dish.name_ru,
            until=until,
            canteen=canteen.name if canteen else "",
        )
        sent += note is not None
    return sent


def expire_promotions(db: Session) -> int:
    """Worker, every 10 minutes: discounts whose time is over become `expired`."""
    result = db.execute(
        update(Promotion)
        .where(
            Promotion.status.in_([PromotionStatus.active, PromotionStatus.proposed]),
            Promotion.valid_to < clock.now_utc(),
        )
        .values(status=PromotionStatus.expired)
    )
    db.commit()
    return result.rowcount
