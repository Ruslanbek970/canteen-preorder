"""Synthetic sales history for the demo (SPEC 5.4): 8 weeks of orders, waste and reviews.

The numbers follow simple, learnable patterns so reports and the forecast (phase 9) have
something to show: a weekday effect, a slow growth of pre-orders, peaks in the breaks
between classes, a dish-specific day (plov on Thursdays) and random noise. Everything
generated here is marked: synthetic customers are inactive `@synthetic.demo` accounts and
`canteens.synthetic_history_until` tells the reports where the synthetic part ends.

python -m ml.synthetic_history          # fill missing past weekdays for every active canteen
"""

import logging
import math
import random
import secrets
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, insert, or_, select, text, update
from sqlalchemy.orm import Session

from app.models import (
    Canteen,
    Dish,
    DishReview,
    MenuItem,
    Order,
    OrderChannel,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PickupSlot,
    StudentGroup,
    User,
    UserAllergen,
    UserRole,
    WasteReason,
    WasteRecord,
)
from app.security import hash_password
from app.services import allergens, slots
from app.utils import time as clock

log = logging.getLogger("synthetic_history")

WEEKS = 8
SYNTHETIC_DOMAIN = "synthetic.demo"
SYNTHETIC_CUSTOMERS = 150

# Mean daily demand per dish on an ordinary Monday, and its average rating.
DISH_PROFILE: dict[str, tuple[int, float]] = {
    "Куриный суп": (48, 4.3),
    "Борщ": (34, 4.1),
    "Лагман": (72, 4.5),
    "Плов": (85, 4.6),
    "Манты": (40, 4.4),
    "Оливье": (27, 3.8),
    "Овощной салат": (19, 4.0),
    "Самса": (95, 4.2),
    "Медовик": (23, 4.7),
    "Чай с молоком": (120, 4.0),
    "Компот": (75, 3.6),
}
DEFAULT_PROFILE = (30, 4.0)
WEEKDAY_FACTOR = {0: 1.0, 1: 1.08, 2: 1.12, 3: 1.0, 4: 0.78}
THURSDAY_PLOV = 1.35
NOISE_SIGMA = 0.15

# Breaks between classes in the demo timetable: (from, to, weight of a slot inside).
BREAKS = [
    (time(10, 20), time(10, 30), 3.0),
    (time(11, 50), time(12, 30), 5.0),
    (time(12, 50), time(13, 20), 4.0),
    (time(13, 30), time(14, 0), 2.5),
    (time(15, 0), time(15, 30), 1.5),
]
OFF_BREAK_WEIGHT = 0.6

PREORDER_SHARE_START, PREORDER_SHARE_END = 0.42, 0.62
NO_SHOW_RATE = 0.04
CANCEL_RATE = 0.03
REVIEW_RATE = 0.12

COMMENTS = {
    1: ["Холодное и невкусное.", "Не понравилось, больше не возьму."],
    2: ["Пересолено.", "Порция маленькая для такой цены."],
    3: ["Нормально, но бывало лучше.", "Обычно.", "Съедобно."],
    4: ["Вкусно, спасибо!", "Хорошо, но можно горячее.", "Неплохо."],
    5: ["Очень вкусно!", "Лучшее в столовой.", "Беру каждый раз.", "Как дома!"],
}


@dataclass
class DayStats:
    orders: int = 0
    portions: int = 0
    wasted: int = 0
    reviews: int = 0


@dataclass
class Result:
    days: list[date] = field(default_factory=list)
    stats: DayStats = field(default_factory=DayStats)


def slot_weight(start: time) -> float:
    for begin, end, weight in BREAKS:
        if begin <= start < end:
            return weight
    return OFF_BREAK_WEIGHT


def expected_demand(dish_name: str, day: date, progress: float) -> float:
    """Mean demand for a dish on a day; `progress` goes from 0 (oldest day) to 1 (yesterday)."""
    base, _ = DISH_PROFILE.get(dish_name, DEFAULT_PROFILE)
    factor = WEEKDAY_FACTOR.get(day.weekday(), 0.0)
    if dish_name == "Плов" and day.weekday() == 3:
        factor *= THURSDAY_PLOV
    return base * factor * (1 + 0.08 * progress)


def history_days(weeks: int = WEEKS) -> list[date]:
    """Past weekdays to cover: the last `weeks` weeks, up to yesterday."""
    today = clock.today_local()
    start = today - timedelta(days=7 * weeks)
    return [
        start + timedelta(days=i)
        for i in range((today - start).days)
        if (start + timedelta(days=i)).weekday() < 5
    ]


def ensure_customers(db: Session, count: int = SYNTHETIC_CUSTOMERS) -> list[int]:
    """Inactive accounts that place the synthetic orders; they cannot sign in."""
    existing = list(
        db.scalars(
            select(User.id).where(User.email.like(f"%@{SYNTHETIC_DOMAIN}")).order_by(User.id)
        )
    )
    if len(existing) >= count:
        return existing[:count]
    pw = hash_password(secrets.token_urlsafe(16))
    groups = list(db.scalars(select(StudentGroup.id).order_by(StudentGroup.id)))
    for i in range(len(existing), count):
        # Students need a group; every fifth customer (or all, without groups) is a teacher.
        student = bool(groups) and i % 5 != 4
        db.add(
            User(
                email=f"customer{i + 1:03d}@{SYNTHETIC_DOMAIN}",
                full_name=f"Покупатель {i + 1:03d}",
                password_hash=pw,
                role=UserRole.student if student else UserRole.teacher,
                group_id=groups[i % len(groups)] if student else None,
                is_active=False,
            )
        )
    db.flush()
    return ensure_customers(db, count)


def _demo_customers(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(
                User.is_active,
                User.role.in_([UserRole.student, UserRole.teacher]),
                User.email.like("%@demo.kz"),
                ~User.email.like("e2e-%"),
            )
            .order_by(User.id)
        )
    )


def _unsafe_dishes(db: Session, users: list[User], dish_ids: list[int]) -> dict[int, set[int]]:
    """Dishes each demo customer must not get: any allergen they have, mild ones too."""
    by_dish = allergens.dish_allergens(db, dish_ids)
    result: dict[int, set[int]] = {}
    for user in users:
        mine = set(
            db.scalars(select(UserAllergen.allergen_id).where(UserAllergen.user_id == user.id))
        )
        result[user.id] = {d for d, items in by_dish.items() if mine & {a.id for a in items}}
    return result


class _Day:
    """Builds the rows of one day; nothing is written until `write`."""

    def __init__(self, rng: random.Random, day: date, canteen: Canteen) -> None:
        self.rng, self.day, self.canteen = rng, day, canteen
        self.orders: list[dict] = []
        self.items: list[list[dict]] = []
        self.counters = {"A": 0, "K": 0}

    def at(self, t: time, minutes: float = 0.0) -> datetime:
        return clock.combine_local(self.day, t) + timedelta(minutes=minutes)

    def number(self, prefix: str) -> str:
        self.counters[prefix] += 1
        return f"{prefix}-{self.counters[prefix]:03d}"

    def add(self, order: dict, lines: list[tuple[MenuItem, int]]) -> None:
        subtotal = sum((mi.price * q for mi, q in lines), Decimal(0))
        order |= {
            "canteen_id": self.canteen.id,
            "service_date": self.day,
            "subtotal": subtotal,
            "discount_total": Decimal(0),
        }
        self.orders.append(order)
        self.items.append(
            [{"menu_item_id": mi.id, "quantity": q, "unit_price": mi.price} for mi, q in lines]
        )


def _split_into_orders(
    rng: random.Random, sold: dict[int, int], allowed: set[int] | None = None
) -> list[list[tuple[int, int]]]:
    """Turns portions sold per menu item into baskets of 1-3 dishes."""
    remaining = {k: v for k, v in sold.items() if v > 0}
    baskets = []
    while remaining:
        size = rng.choice([1, 1, 1, 2, 2, 3])
        basket: dict[int, int] = {}
        for _ in range(size):
            pool = [k for k in remaining if k not in basket and (allowed is None or k in allowed)]
            if not pool:
                break
            pick = rng.choices(pool, weights=[remaining[k] for k in pool])[0]
            qty = 2 if remaining[pick] >= 2 and rng.random() < 0.12 else 1
            basket[pick] = qty
            remaining[pick] -= qty
            if remaining[pick] == 0:
                del remaining[pick]
        if not basket:
            break
        baskets.append(list(basket.items()))
    return baskets


def generate_day(
    db: Session,
    rng: random.Random,
    canteen: Canteen,
    day: date,
    progress: float,
    customers: list[int],
    demo: list[User],
    unsafe: dict[int, set[int]],
    cook_id: int | None,
) -> DayStats:
    slots.generate_slots(db, canteen, day)
    day_slots = list(
        db.scalars(
            select(PickupSlot)
            .where(PickupSlot.canteen_id == canteen.id, PickupSlot.slot_date == day)
            .order_by(PickupSlot.starts_at)
        )
    )
    dishes = list(db.scalars(select(Dish).where(Dish.is_active).order_by(Dish.id)))
    items = {
        mi.dish_id: mi
        for mi in db.scalars(
            select(MenuItem).where(MenuItem.canteen_id == canteen.id, MenuItem.menu_date == day)
        )
    }
    planned: dict[int, int] = {}
    sold: dict[int, int] = {}
    for dish in dishes:
        mean = expected_demand(dish.name_ru, day, progress)
        if mean <= 0:
            continue
        # What the kitchen cooked before the forecast existed: a rough guess with a margin.
        plan = max(5, round(mean * rng.uniform(1.0, 1.3)))
        demand = round(mean * math.exp(rng.gauss(-(NOISE_SIGMA**2) / 2, NOISE_SIGMA)))
        mi = items.get(dish.id)
        if mi is None:
            mi = MenuItem(
                canteen_id=canteen.id,
                dish_id=dish.id,
                menu_date=day,
                price=dish.base_price,
                planned_portions=plan,
                available_portions=plan,
                cooked_at=clock.combine_local(day, time(8, 30)),
            )
            db.add(mi)
            db.flush()
            items[dish.id] = mi
        planned[mi.id] = mi.planned_portions
        sold[mi.id] = min(mi.planned_portions, demand)
    by_id = {mi.id: mi for mi in items.values() if mi.id in planned}
    if not by_id:
        return DayStats()

    build = _Day(rng, day, canteen)
    weights = [slot_weight(s.starts_at) for s in day_slots]
    booked: dict[int, int] = defaultdict(int)

    def pick_slot() -> PickupSlot | None:
        for _ in range(10):
            slot = rng.choices(day_slots, weights=weights)[0]
            if booked[slot.id] < slot.capacity:
                return slot
        return None

    def app_order(user_id: int, basket: list[tuple[int, int]], status: OrderStatus) -> None:
        slot = pick_slot()
        if slot is None:
            cashier_order(basket)
            return
        start = clock.combine_local(day, slot.starts_at)
        created = start - timedelta(minutes=rng.uniform(15, 180))
        paid = created + timedelta(minutes=rng.uniform(0.5, 3))
        order = {
            "order_number": build.number("A"),
            "user_id": user_id,
            "pickup_slot_id": slot.id,
            "channel": OrderChannel.mobile_app,
            "status": status,
            "created_at": created,
            "paid_at": None if status == OrderStatus.cancelled else paid,
            "ready_at": None,
            "picked_up_at": None,
            "_pay": PaymentMethod.kaspi_qr,
            "_slot_end": clock.combine_local(day, slot.ends_at),
        }
        if status in (OrderStatus.picked_up, OrderStatus.no_show):
            order["ready_at"] = start - timedelta(minutes=rng.uniform(1, 8))
        if status == OrderStatus.picked_up:
            order["picked_up_at"] = start + timedelta(minutes=rng.uniform(0, 9))
        if status != OrderStatus.cancelled:
            booked[slot.id] += 1
        build.add(order, [(by_id[k], q) for k, q in basket])

    def cashier_order(basket: list[tuple[int, int]]) -> None:
        slot = rng.choices(day_slots, weights=weights)[0] if day_slots else None
        at = build.at(slot.starts_at if slot else time(12, 0), rng.uniform(0, 10))
        order = {
            "order_number": build.number("K"),
            "user_id": None,
            "pickup_slot_id": None,
            "channel": OrderChannel.cashier,
            "status": OrderStatus.picked_up,
            "created_at": at,
            "paid_at": at,
            "ready_at": None,
            "picked_up_at": at,
            "_pay": rng.choice([PaymentMethod.cash, PaymentMethod.kaspi_qr]),
        }
        build.add(order, [(by_id[k], q) for k, q in basket])

    # Demo accounts get a light, allergy-safe history of their own.
    for user in demo:
        chance = 0.5 if user.email in ("student@demo.kz", "teacher@demo.kz") else 0.2
        if rng.random() >= chance:
            continue
        safe = {k for k, mi in by_id.items() if mi.dish_id not in unsafe.get(user.id, set())}
        pool = {k: sold[k] for k in safe if sold[k] > 0}
        baskets = _split_into_orders(rng, pool, safe)
        if baskets:
            basket = baskets[0]
            for k, q in basket:
                sold[k] -= q
            app_order(user.id, basket, OrderStatus.picked_up)

    share = PREORDER_SHARE_START + (PREORDER_SHARE_END - PREORDER_SHARE_START) * progress
    for basket in _split_into_orders(rng, sold):
        if rng.random() < share:
            status = OrderStatus.no_show if rng.random() < NO_SHOW_RATE else OrderStatus.picked_up
            app_order(rng.choice(customers), basket, status)
        else:
            cashier_order(basket)
    # Cancelled orders do not consume portions; they only show up in the counts.
    for _ in range(round(len(build.orders) * CANCEL_RATE)):
        k = rng.choice(list(by_id))
        app_order(rng.choice(customers), [(k, 1)], OrderStatus.cancelled)

    return _write(db, rng, build, by_id, planned, booked, cook_id)


def _write(
    db: Session,
    rng: random.Random,
    build: _Day,
    by_id: dict[int, MenuItem],
    planned: dict[int, int],
    booked: dict[int, int],
    cook_id: int | None,
) -> DayStats:
    stats = DayStats(orders=len(build.orders))
    meta = [{k: o.pop(k) for k in list(o) if k.startswith("_")} for o in build.orders]
    order_ids = list(
        db.scalars(insert(Order).returning(Order.id, sort_by_parameter_order=True), build.orders)
    )
    item_rows = []
    owners = []
    for order_id, lines in zip(order_ids, build.items, strict=True):
        for line in lines:
            item_rows.append(line | {"order_id": order_id})
            owners.append(order_id)
    item_ids = list(
        db.scalars(
            insert(OrderItem).returning(OrderItem.id, sort_by_parameter_order=True), item_rows
        )
    )
    # The status trigger stamps history with now(); move it to when it happened.
    db.execute(
        text(
            "UPDATE order_status_history h SET changed_at = "
            "COALESCE(o.picked_up_at, o.ready_at, o.paid_at, o.created_at) "
            "FROM orders o WHERE h.order_id = o.id AND o.id = ANY(:ids)"
        ),
        {"ids": order_ids},
    )

    payments = []
    sold_portions: dict[int, int] = defaultdict(int)
    waste: list[dict] = []
    reviews: list[dict] = []
    for order_id, order, extra, lines in zip(
        order_ids, build.orders, meta, build.items, strict=True
    ):
        total = order["subtotal"]
        cancelled = order["status"] == OrderStatus.cancelled
        payments.append(
            {
                "order_id": order_id,
                "method": extra["_pay"],
                "amount": total,
                "status": PaymentStatus.failed if cancelled else PaymentStatus.succeeded,
                "provider_transaction_id": None if cancelled else f"synthetic-{order_id}",
                "fiscal_receipt_number": None if cancelled else f"MOCK-S{order_id:08d}",
                "created_at": order["created_at"],
                "completed_at": order["created_at"] if cancelled else order["paid_at"],
            }
        )
        if cancelled:
            continue
        for line in lines:
            sold_portions[line["menu_item_id"]] += line["quantity"]
            stats.portions += line["quantity"]
        if order["status"] == OrderStatus.no_show:
            for line in lines:
                waste.append(
                    {
                        "menu_item_id": line["menu_item_id"],
                        "portions": line["quantity"],
                        "reason": WasteReason.uncollected_order,
                        "order_id": order_id,
                        "recorded_at": extra["_slot_end"] + timedelta(minutes=35),
                    }
                )
    db.execute(insert(Payment), payments)

    position = {order_id: i for i, order_id in enumerate(order_ids)}
    for item_id, order_id, row in zip(item_ids, owners, item_rows, strict=True):
        order = build.orders[position[order_id]]
        if order["user_id"] is None or order["status"] != OrderStatus.picked_up:
            continue
        if rng.random() >= REVIEW_RATE:
            continue
        dish_name = by_id[row["menu_item_id"]].dish.name_ru
        mean = DISH_PROFILE.get(dish_name, DEFAULT_PROFILE)[1]
        rating = min(5, max(1, round(rng.gauss(mean, 0.8))))
        reviews.append(
            {
                "order_item_id": item_id,
                "rating": rating,
                "comment": rng.choice(COMMENTS[rating]) if rng.random() < 0.4 else None,
                "created_at": order["picked_up_at"] + timedelta(hours=rng.uniform(0.5, 30)),
            }
        )
    if reviews:
        db.execute(insert(DishReview), reviews)
    stats.reviews = len(reviews)

    close = build.at(build.canteen.closes_at)
    for mi_id, mi in by_id.items():
        left = planned[mi_id] - sold_portions[mi_id]
        if left > 0 and rng.random() < 0.1:
            damaged = min(left, rng.randint(1, 3))
            waste.append(
                {
                    "menu_item_id": mi_id,
                    "portions": damaged,
                    "reason": WasteReason.damaged,
                    "recorded_by": cook_id,
                    "recorded_at": close - timedelta(hours=rng.uniform(1, 5)),
                }
            )
            left -= damaged
        expired = left if mi.dish.shelf_life_hours < 24 else left // 3
        if expired > 0:
            waste.append(
                {
                    "menu_item_id": mi_id,
                    "portions": expired,
                    "reason": WasteReason.expired,
                    "recorded_by": cook_id,
                    "recorded_at": close,
                }
            )
        mi.available_portions = left - expired
    for row in waste:
        row.setdefault("order_id", None)
        row.setdefault("recorded_by", None)
    if waste:
        db.execute(insert(WasteRecord), waste)
    stats.wasted = sum(w["portions"] for w in waste)
    for slot_id, count in booked.items():
        db.execute(update(PickupSlot).where(PickupSlot.id == slot_id).values(booked_count=count))
    db.commit()
    return stats


def generate(db: Session, canteen: Canteen, weeks: int = WEEKS, seed: int = 42) -> Result:
    """Idempotent: days that already have orders (real or synthetic) are skipped."""
    days = history_days(weeks)
    if not days:
        return Result()
    busy = set(
        db.scalars(
            select(Order.service_date)
            .where(Order.canteen_id == canteen.id, Order.service_date.in_(days))
            .distinct()
        )
    )
    todo = [d for d in days if d not in busy]
    result = Result(days=todo)
    if not todo:
        return result
    customers = ensure_customers(db)
    demo = _demo_customers(db)
    dish_ids = list(db.scalars(select(Dish.id).where(Dish.is_active)))
    unsafe = _unsafe_dishes(db, demo, dish_ids)
    cook_id = db.scalar(
        select(User.id).where(User.role == UserRole.cook, User.canteen_id == canteen.id).limit(1)
    )
    first = days[0]
    span = max(1, (days[-1] - first).days)
    for day in todo:
        # One generator per day keeps a day's numbers stable whatever else was generated.
        rng = random.Random(f"{seed}-{canteen.id}-{day.isoformat()}")
        stats = generate_day(
            db, rng, canteen, day, (day - first).days / span, customers, demo, unsafe, cook_id
        )
        result.stats.orders += stats.orders
        result.stats.portions += stats.portions
        result.stats.wasted += stats.wasted
        result.stats.reviews += stats.reviews
    canteen.synthetic_history_until = max(todo[-1], canteen.synthetic_history_until or todo[-1])
    db.commit()
    log.info(
        "synthetic history for %s: %s days, %s orders, %s portions, %s wasted, %s reviews",
        canteen.name,
        len(todo),
        result.stats.orders,
        result.stats.portions,
        result.stats.wasted,
        result.stats.reviews,
    )
    return result


def generate_for_active(db: Session, weeks: int = WEEKS) -> int:
    total = 0
    for canteen in db.scalars(
        select(Canteen)
        .where(Canteen.is_active, or_(Canteen.slug.is_(None), Canteen.slug != "e2e"))
        .order_by(Canteen.id)
    ).all():
        total += len(generate(db, canteen, weeks).days)
    return total


def has_history(db: Session) -> bool:
    return bool(
        db.scalar(
            select(func.count(Canteen.id)).where(Canteen.synthetic_history_until.is_not(None))
        )
    )


def main() -> None:
    from app.db import SessionLocal

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as db:
        days = generate_for_active(db)
    print(f"Synthetic history: {days} days generated.")


if __name__ == "__main__":
    main()
