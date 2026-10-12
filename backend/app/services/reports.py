"""Manager dashboard and reports (SPEC 8.8, 9.4): sales, waste, peak slots, ratings, CSV.
The forecast report itself lives in `forecast_report`."""

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.errors import NotFoundError, ValidationError
from app.models import (
    Canteen,
    Dish,
    DishReview,
    MenuItem,
    Order,
    OrderChannel,
    OrderItem,
    OrderStatus,
    PickupSlot,
    Promotion,
    PromotionStatus,
    WasteReason,
    WasteRecord,
)
from app.schemas.reports import (
    Dashboard,
    DashboardSlot,
    DishRating,
    PeakReport,
    PeakSlot,
    PeakWeekday,
    RatingComment,
    RatingsReport,
    SalesDay,
    SalesDish,
    SalesReport,
    SalesTotals,
    WasteDay,
    WasteDish,
    WasteReport,
)
from app.utils import time as clock

# Orders that were paid for: they count as sales (a no-show was paid, then thrown away).
SOLD = (
    OrderStatus.paid,
    OrderStatus.cooking,
    OrderStatus.ready,
    OrderStatus.picked_up,
    OrderStatus.no_show,
)
DEFAULT_DAYS = 28
MAX_DAYS = 366
REPORTS = ("sales", "waste", "peak-hours", "ratings", "forecast")


def period(from_date: date | None, to_date: date | None, days: int = DEFAULT_DAYS):
    """Inclusive range; by default the last `days` days up to today."""
    to_date = to_date or clock.today_local()
    from_date = from_date or to_date - timedelta(days=days - 1)
    if from_date > to_date:
        raise ValidationError("invalid_period", "Начало периода позже конца")
    if (to_date - from_date).days + 1 > MAX_DAYS:
        raise ValidationError("period_too_long", f"Период не длиннее {MAX_DAYS} дней")
    return from_date, to_date


def _synthetic_until(db: Session, canteen_id: int) -> date | None:
    return db.scalar(select(Canteen.synthetic_history_until).where(Canteen.id == canteen_id))


def _share(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def dashboard(db: Session, canteen_id: int) -> Dashboard:
    today = clock.today_local()
    by_status = dict(
        db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.canteen_id == canteen_id, Order.service_date == today)
            .group_by(Order.status)
        ).all()
    )
    sold = select(Order.id).where(
        Order.canteen_id == canteen_id, Order.service_date == today, Order.status.in_(SOLD)
    )
    revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.id.in_(sold)))
    portions = db.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(OrderItem.order_id.in_(sold))
    )
    channels = dict(
        db.execute(
            select(Order.channel, func.count(Order.id))
            .where(Order.id.in_(sold))
            .group_by(Order.channel)
        ).all()
    )
    cashier_sales = channels.pop(OrderChannel.cashier, 0)
    waste = dict(
        db.execute(
            select(WasteRecord.reason, func.sum(WasteRecord.portions))
            .join(MenuItem, MenuItem.id == WasteRecord.menu_item_id)
            .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date == today)
            .group_by(WasteRecord.reason)
        ).all()
    )
    slots = db.scalars(
        select(PickupSlot)
        .where(PickupSlot.canteen_id == canteen_id, PickupSlot.slot_date == today)
        .order_by(PickupSlot.starts_at)
    ).all()
    proposed = db.scalar(
        select(func.count(Promotion.id))
        .outerjoin(MenuItem, MenuItem.id == Promotion.menu_item_id)
        .outerjoin(PickupSlot, PickupSlot.id == Promotion.pickup_slot_id)
        .where(
            Promotion.status == PromotionStatus.proposed,
            func.coalesce(MenuItem.canteen_id, PickupSlot.canteen_id) == canteen_id,
        )
    )
    preorders = sum(channels.values())
    no_show = by_status.get(OrderStatus.no_show, 0)
    # Share among pre-orders that are over: till sales are always picked up.
    finished = no_show + by_status.get(OrderStatus.picked_up, 0) - cashier_sales
    return Dashboard(
        date=today,
        orders_total=sum(by_status.values()),
        orders_by_status={s.value: by_status.get(s, 0) for s in OrderStatus},
        preorders=preorders,
        cashier_sales=cashier_sales,
        revenue=Decimal(revenue),
        portions_sold=int(portions),
        waste_portions=int(sum(waste.values())),
        waste_by_reason={r.value: int(waste.get(r, 0)) for r in WasteReason},
        no_show=no_show,
        no_show_percent=_share(no_show, finished),
        proposed_promotions=proposed or 0,
        slots=[
            DashboardSlot(
                id=s.id,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                capacity=s.capacity,
                booked=s.booked_count,
                is_closed=s.is_closed,
            )
            for s in slots
        ],
        synthetic_history_until=_synthetic_until(db, canteen_id),
    )


def _sold_orders(canteen_id: int, from_date: date, to_date: date):
    return (
        Order.canteen_id == canteen_id,
        Order.service_date.between(from_date, to_date),
        Order.status.in_(SOLD),
    )


def sales(db: Session, canteen_id: int, from_date: date, to_date: date) -> SalesReport:
    where = _sold_orders(canteen_id, from_date, to_date)
    preorder = case((Order.channel != OrderChannel.cashier, 1), else_=0)
    order_rows = db.execute(
        select(
            Order.service_date,
            func.count(Order.id),
            func.sum(Order.total),
            func.sum(preorder),
        )
        .where(*where)
        .group_by(Order.service_date)
        .order_by(Order.service_date)
    ).all()
    portion_rows = dict(
        db.execute(
            select(Order.service_date, func.sum(OrderItem.quantity))
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(*where)
            .group_by(Order.service_date)
        ).all()
    )
    days = [
        SalesDay(
            date=d,
            orders=n,
            portions=int(portion_rows.get(d, 0)),
            revenue=Decimal(revenue),
            preorder_share=_share(int(pre), n),
        )
        for d, n, revenue, pre in order_rows
    ]
    dish_rows = db.execute(
        select(
            Dish.id,
            Dish.name_ru,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.unit_price * OrderItem.quantity - OrderItem.discount_amount),
        )
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Dish, Dish.id == MenuItem.dish_id)
        .where(*where)
        .group_by(Dish.id, Dish.name_ru)
        .order_by(func.sum(OrderItem.quantity).desc(), Dish.name_ru)
    ).all()
    orders = sum(d.orders for d in days)
    revenue = sum((d.revenue for d in days), Decimal(0))
    preorders = sum(int(pre) for *_, pre in order_rows)
    return SalesReport(
        from_date=from_date,
        to_date=to_date,
        totals=SalesTotals(
            orders=orders,
            portions=sum(d.portions for d in days),
            revenue=revenue,
            average_check=(revenue / orders).quantize(Decimal("0.01")) if orders else None,
            preorder_share=_share(preorders, orders),
        ),
        days=days,
        dishes=[
            SalesDish(dish_id=i, name=n, portions=int(p), revenue=Decimal(r))
            for i, n, p, r in dish_rows
        ],
        synthetic_history_until=_synthetic_until(db, canteen_id),
    )


def waste(db: Session, canteen_id: int, from_date: date, to_date: date) -> WasteReport:
    in_period = (
        MenuItem.canteen_id == canteen_id,
        MenuItem.menu_date.between(from_date, to_date),
    )
    rows = db.execute(
        select(MenuItem.menu_date, WasteRecord.reason, func.sum(WasteRecord.portions))
        .join(MenuItem, MenuItem.id == WasteRecord.menu_item_id)
        .where(*in_period)
        .group_by(MenuItem.menu_date, WasteRecord.reason)
        .order_by(MenuItem.menu_date)
    ).all()
    per_day: dict[date, dict[str, int]] = defaultdict(dict)
    by_reason: dict[str, int] = {r.value: 0 for r in WasteReason}
    for d, reason, portions in rows:
        per_day[d][reason.value] = int(portions)
        by_reason[reason.value] += int(portions)
    wasted = (
        select(WasteRecord.menu_item_id, func.sum(WasteRecord.portions).label("portions"))
        .group_by(WasteRecord.menu_item_id)
        .subquery()
    )
    dish_rows = db.execute(
        select(
            Dish.id,
            Dish.name_ru,
            func.coalesce(func.sum(wasted.c.portions), 0),
            func.sum(MenuItem.planned_portions),
        )
        .select_from(MenuItem)
        .join(Dish, Dish.id == MenuItem.dish_id)
        .outerjoin(wasted, wasted.c.menu_item_id == MenuItem.id)
        .where(*in_period)
        .group_by(Dish.id, Dish.name_ru)
        .order_by(func.coalesce(func.sum(wasted.c.portions), 0).desc(), Dish.name_ru)
    ).all()
    menu_days = (
        db.scalar(select(func.count(func.distinct(MenuItem.menu_date))).where(*in_period)) or 0
    )
    total = sum(by_reason.values())
    planned = sum(int(p) for *_, p in dish_rows)
    return WasteReport(
        from_date=from_date,
        to_date=to_date,
        total=total,
        per_day=round(total / menu_days, 1) if menu_days else None,
        percent_of_planned=_share(total, planned),
        by_reason=by_reason,
        days=[WasteDay(date=d, portions=sum(r.values()), by_reason=r) for d, r in per_day.items()],
        dishes=[
            WasteDish(
                dish_id=i,
                name=n,
                portions=int(w),
                planned=int(p),
                percent_of_planned=_share(int(w), int(p)),
            )
            for i, n, w, p in dish_rows
        ],
        synthetic_history_until=_synthetic_until(db, canteen_id),
    )


def peak_hours(db: Session, canteen_id: int, from_date: date, to_date: date) -> PeakReport:
    where = (
        Order.canteen_id == canteen_id,
        Order.service_date.between(from_date, to_date),
        Order.status.in_(SOLD),
    )
    days = db.scalar(select(func.count(func.distinct(Order.service_date))).where(*where)) or 0
    slot_rows = db.execute(
        select(PickupSlot.starts_at, func.count(Order.id))
        .join(Order, Order.pickup_slot_id == PickupSlot.id)
        .where(*where)
        .group_by(PickupSlot.starts_at)
        .order_by(PickupSlot.starts_at)
    ).all()
    capacity = dict(
        db.execute(
            select(PickupSlot.starts_at, func.sum(PickupSlot.capacity))
            .where(
                PickupSlot.canteen_id == canteen_id,
                PickupSlot.slot_date.in_(
                    select(Order.service_date).where(*where).distinct().scalar_subquery()
                ),
            )
            .group_by(PickupSlot.starts_at)
        ).all()
    )
    weekday = func.extract("isodow", Order.service_date)
    weekday_rows = db.execute(
        select(
            weekday,
            func.count(Order.id),
            func.count(func.distinct(Order.service_date)),
        )
        .where(*where)
        .group_by(weekday)
        .order_by(weekday)
    ).all()
    finished = dict(
        db.execute(
            select(Order.status, func.count(Order.id))
            .where(
                *where[:2],
                Order.channel != OrderChannel.cashier,
                Order.status.in_([OrderStatus.picked_up, OrderStatus.no_show]),
            )
            .group_by(Order.status)
        ).all()
    )
    no_show = finished.get(OrderStatus.no_show, 0)
    return PeakReport(
        from_date=from_date,
        to_date=to_date,
        days=days,
        no_show_percent=_share(no_show, no_show + finished.get(OrderStatus.picked_up, 0)),
        slots=[
            PeakSlot(
                starts_at=start,
                orders=n,
                per_day=round(n / days, 1) if days else 0.0,
                load_percent=_share(n, int(capacity.get(start, 0))),
            )
            for start, n in slot_rows
        ],
        weekdays=[
            PeakWeekday(weekday=int(w), orders=n, per_day=round(n / d, 1))
            for w, n, d in weekday_rows
        ],
        synthetic_history_until=_synthetic_until(db, canteen_id),
    )


def ratings(db: Session, canteen_id: int, from_date: date, to_date: date) -> RatingsReport:
    base = (
        select(DishReview, Dish.id, Dish.name_ru)
        .join(OrderItem, OrderItem.id == DishReview.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .join(Dish, Dish.id == MenuItem.dish_id)
        .where(Order.canteen_id == canteen_id, Order.service_date.between(from_date, to_date))
        .order_by(DishReview.created_at.desc(), DishReview.id.desc())
    )
    by_dish: dict[int, DishRating] = {}
    totals: dict[int, int] = defaultdict(int)
    for review, dish_id, name in db.execute(base).all():
        entry = by_dish.setdefault(
            dish_id,
            DishRating(
                dish_id=dish_id,
                name=name,
                rating=None,
                count=0,
                distribution=[0] * 5,
                last_comments=[],
            ),
        )
        entry.count += 1
        entry.distribution[review.rating - 1] += 1
        totals[dish_id] += review.rating
        if review.comment and len(entry.last_comments) < 3:
            entry.last_comments.append(
                RatingComment(
                    rating=review.rating, comment=review.comment, created_at=review.created_at
                )
            )
    for dish_id, entry in by_dish.items():
        entry.rating = round(totals[dish_id] / entry.count, 2)
    return RatingsReport(
        from_date=from_date,
        to_date=to_date,
        dishes=sorted(by_dish.values(), key=lambda r: (-(r.rating or 0), r.name)),
        synthetic_history_until=_synthetic_until(db, canteen_id),
    )


def _csv(header: list[str], rows: list[list[object]]) -> str:
    out = io.StringIO()
    # BOM so Excel opens Cyrillic correctly.
    out.write("﻿")
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def report_csv(
    db: Session, canteen_id: int, name: str, from_date: date, to_date: date
) -> tuple[str, str]:
    """(file name, CSV text) for any report."""
    if name not in REPORTS:
        raise NotFoundError("report", "Такого отчёта нет")
    filename = f"{name}_{from_date.isoformat()}_{to_date.isoformat()}.csv"
    if name == "sales":
        rows = db.execute(
            select(
                Order.service_date,
                Dish.name_ru,
                func.sum(OrderItem.quantity),
                func.sum(OrderItem.unit_price * OrderItem.quantity - OrderItem.discount_amount),
            )
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
            .join(Dish, Dish.id == MenuItem.dish_id)
            .where(*_sold_orders(canteen_id, from_date, to_date))
            .group_by(Order.service_date, Dish.name_ru)
            .order_by(Order.service_date, Dish.name_ru)
        ).all()
        return filename, _csv(["date", "dish", "portions", "revenue"], [list(r) for r in rows])
    if name == "waste":
        rows = db.execute(
            select(MenuItem.menu_date, Dish.name_ru, WasteRecord.reason, WasteRecord.portions)
            .join(MenuItem, MenuItem.id == WasteRecord.menu_item_id)
            .join(Dish, Dish.id == MenuItem.dish_id)
            .where(
                MenuItem.canteen_id == canteen_id,
                MenuItem.menu_date.between(from_date, to_date),
            )
            .order_by(MenuItem.menu_date, Dish.name_ru, WasteRecord.id)
        ).all()
        return filename, _csv(
            ["date", "dish", "reason", "portions"], [[d, n, r.value, p] for d, n, r, p in rows]
        )
    if name == "forecast":
        from app.services.forecast_report import forecast_rows

        rows = [
            [day, dish, sold, served, p.get("baseline_avg"), p.get("gbm_v1")]
            for day, _, dish, sold, served, p in forecast_rows(db, canteen_id, from_date, to_date)
        ]
        return filename, _csv(
            ["date", "dish", "actual", "forecast", "baseline_avg", "gbm_v1"], rows
        )
    if name == "peak-hours":
        report = peak_hours(db, canteen_id, from_date, to_date)
        return filename, _csv(
            ["slot", "orders", "per_day", "load_percent"],
            [
                [s.starts_at.strftime("%H:%M"), s.orders, s.per_day, s.load_percent]
                for s in report.slots
            ],
        )
    report = ratings(db, canteen_id, from_date, to_date)
    return filename, _csv(
        ["dish", "rating", "reviews", "1", "2", "3", "4", "5"],
        [[d.name, d.rating, d.count, *d.distribution] for d in report.dishes],
    )
