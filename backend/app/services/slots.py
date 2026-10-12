"""Pickup slots: generation, schedule filter and manager settings (SPEC 7.4)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import Canteen, ClassSchedule, PickupSlot, User, UserRole
from app.schemas.slots import SlotOut, SlotPatch, SlotsHidden, SlotsResponse
from app.services import pricing
from app.utils import time as clock


def slot_times(canteen: Canteen) -> list[tuple[time, time]]:
    """Slots from opens_at to closes_at with the canteen's default length."""
    step = timedelta(minutes=canteen.default_slot_minutes)
    day = date(2000, 1, 3)
    current = datetime.combine(day, canteen.opens_at)
    end = datetime.combine(day, canteen.closes_at)
    result = []
    while current + step <= end:
        result.append((current.time(), (current + step).time()))
        current += step
    return result


def generate_slots(db: Session, canteen: Canteen, day: date) -> int:
    """Idempotent: existing slots (and their bookings) are left untouched."""
    rows = [
        {
            "canteen_id": canteen.id,
            "slot_date": day,
            "starts_at": start,
            "ends_at": end,
            "capacity": canteen.default_slot_capacity,
        }
        for start, end in slot_times(canteen)
    ]
    if not rows:
        return 0
    result = db.execute(
        insert(PickupSlot)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["canteen_id", "slot_date", "starts_at"])
        .returning(PickupSlot.id)
    )
    created = len(result.all())
    db.commit()
    return created


def generate_for_active(db: Session, days: list[date] | None = None) -> int:
    today = clock.today_local()
    days = days or [today, today + timedelta(days=1)]
    created = 0
    for canteen in db.scalars(select(Canteen).where(Canteen.is_active)).all():
        for day in days:
            created += generate_slots(db, canteen, day)
    return created


def slot_start(slot: PickupSlot) -> datetime:
    return clock.combine_local(slot.slot_date, slot.starts_at)


def slot_end(slot: PickupSlot) -> datetime:
    return clock.combine_local(slot.slot_date, slot.ends_at)


def _overlaps_lessons(user: User, day: date):
    """`(slot) OVERLAPS (lesson)` for the student's group on that weekday (SPEC 7.4)."""
    return exists().where(
        and_(
            ClassSchedule.group_id == user.group_id,
            ClassSchedule.day_of_week == day.isoweekday(),
            ClassSchedule.starts_at < PickupSlot.ends_at,
            ClassSchedule.ends_at > PickupSlot.starts_at,
        )
    )


def applies_schedule(user: User) -> bool:
    return user.role == UserRole.student and user.group_id is not None


@dataclass
class SlotCheck:
    ok: bool
    reason: str | None = None  # closed | too_late | full | by_schedule


def check_slot(db: Session, slot: PickupSlot, canteen: Canteen, user: User) -> SlotCheck:
    if slot.is_closed:
        return SlotCheck(False, "closed")
    cutoff = clock.now_local() + timedelta(minutes=canteen.order_cutoff_minutes)
    if slot_start(slot) < cutoff:
        return SlotCheck(False, "too_late")
    if slot.booked_count >= slot.capacity:
        return SlotCheck(False, "full")
    if applies_schedule(user):
        busy = db.scalar(
            select(_overlaps_lessons(user, slot.slot_date)).where(PickupSlot.id == slot.id)
        )
        if busy:
            return SlotCheck(False, "by_schedule")
    return SlotCheck(True)


def to_out(slot: PickupSlot, promo=None) -> SlotOut:
    return SlotOut(
        id=slot.id,
        slot_date=slot.slot_date,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        capacity=slot.capacity,
        booked_count=slot.booked_count,
        free=max(slot.capacity - slot.booked_count, 0),
        is_closed=slot.is_closed,
        discount_percent=promo.discount_percent if promo else None,
        promotion_id=promo.id if promo else None,
    )


def slots_for_user(db: Session, canteen: Canteen, day: date, user: User) -> SlotsResponse:
    all_slots = list(
        db.scalars(
            select(PickupSlot)
            .where(PickupSlot.canteen_id == canteen.id, PickupSlot.slot_date == day)
            .order_by(PickupSlot.starts_at)
        )
    )
    busy_ids: set[int] = set()
    schedule = applies_schedule(user)
    if schedule and all_slots:
        busy_ids = set(
            db.scalars(
                select(PickupSlot.id).where(
                    PickupSlot.id.in_([s.id for s in all_slots]), _overlaps_lessons(user, day)
                )
            )
        )
    cutoff = clock.now_local() + timedelta(minutes=canteen.order_cutoff_minutes)
    hidden = SlotsHidden()
    visible = []
    for slot in all_slots:
        if slot.is_closed:
            hidden.closed += 1
        elif slot_start(slot) < cutoff:
            hidden.too_late += 1
        elif slot.id in busy_ids:
            hidden.by_schedule += 1
        elif slot.booked_count >= slot.capacity:
            hidden.full += 1
        else:
            visible.append(slot)
    promos = pricing.slot_promotions(db, [s.id for s in visible], clock.now_utc())
    return SlotsResponse(
        canteen_id=canteen.id,
        date=day,
        slots=[to_out(s, promos.get(s.id)) for s in visible],
        hidden=hidden,
        total=len(all_slots),
        cutoff_minutes=canteen.order_cutoff_minutes,
        schedule_applied=schedule,
    )


def manager_slots(db: Session, canteen_id: int, day: date) -> list[SlotOut]:
    slots = list(
        db.scalars(
            select(PickupSlot)
            .where(PickupSlot.canteen_id == canteen_id, PickupSlot.slot_date == day)
            .order_by(PickupSlot.starts_at)
        )
    )
    promos = pricing.slot_promotions(db, [s.id for s in slots], clock.now_utc())
    return [to_out(s, promos.get(s.id)) for s in slots]


def patch_slot(db: Session, canteen_id: int, slot_id: int, data: SlotPatch) -> PickupSlot:
    slot = db.scalar(
        select(PickupSlot)
        .where(PickupSlot.id == slot_id, PickupSlot.canteen_id == canteen_id)
        .with_for_update()
    )
    if slot is None:
        raise NotFoundError("slot", "Слот не найден")
    if data.capacity is not None:
        if data.capacity < slot.booked_count:
            raise ConflictError(
                "capacity_below_booked",
                f"В слоте уже {slot.booked_count} заказов",
                {"booked": slot.booked_count},
            )
        slot.capacity = data.capacity
    if data.is_closed is not None:
        slot.is_closed = data.is_closed
    db.commit()
    return slot


def book(db: Session, slot_id: int) -> bool:
    """Atomic booking (SPEC 5.3): succeeds only while booked_count < capacity."""
    booked = db.execute(
        update(PickupSlot)
        .where(
            PickupSlot.id == slot_id,
            PickupSlot.booked_count < PickupSlot.capacity,
            PickupSlot.is_closed.is_(False),
        )
        .values(booked_count=PickupSlot.booked_count + 1)
        .returning(PickupSlot.id)
    ).first()
    return booked is not None


def release(db: Session, slot_id: int) -> None:
    db.execute(
        update(PickupSlot)
        .where(PickupSlot.id == slot_id, PickupSlot.booked_count > 0)
        .values(booked_count=PickupSlot.booked_count - 1)
    )
