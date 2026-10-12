"""Demand forecast (SPEC 7.13): portions of each dish on the menu of a day.

Two models:
- `baseline_avg`: mean sales of the dish on the same weekday over the last 4 weeks;
- `gbm_v1`: GradientBoostingRegressor on calendar, timetable, price and recent-sales features.

The model with the lower MAE on the last 2 weeks (backtest) is served. A run writes
`menu_items.forecast_portions` / `forecast_model` and one row in `forecast_runs` whose
`details` keep both models' predictions, so the report can compare them with the facts.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Canteen,
    ClassSchedule,
    Dish,
    ForecastRun,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    Promotion,
    PromotionType,
)
from app.utils import time as clock
from ml.metrics import metrics

log = logging.getLogger(__name__)

BASELINE = "baseline_avg"
GBM = "gbm_v1"
MODELS = (BASELINE, GBM)
BACKTEST_DAYS = 14
HORIZON_DAYS = 7  # the nightly job forecasts every menu already planned this far ahead
MIN_TRAIN_ROWS = 50
SOLD = (
    OrderStatus.paid,
    OrderStatus.cooking,
    OrderStatus.ready,
    OrderStatus.picked_up,
    OrderStatus.no_show,
)
FEATURES = (
    "weekday",
    "semester_week",
    "holiday",
    "lessons",
    "price",
    "had_discount",
    "same_category",
    "last_week_sales",
    "dish_id",
)
COLUMNS = ["menu_item_id", "dish_id", "category_id", "menu_date", "price", "had_discount", "sold"]


@dataclass
class Context:
    semester_start: date
    holidays: set[date] = field(default_factory=set)
    lessons: dict[int, int] = field(default_factory=dict)  # ISO weekday -> lessons of all groups


def load_context(db: Session) -> Context:
    settings = get_settings()
    lessons = dict(
        db.execute(
            select(ClassSchedule.day_of_week, func.count(ClassSchedule.id)).group_by(
                ClassSchedule.day_of_week
            )
        ).all()
    )
    return Context(settings.semester_start, settings.holiday_dates, lessons)


def load_menu(db: Session, canteen_id: int, start: date | None, end: date) -> pd.DataFrame:
    """Menu items of the canteen with `start <= menu_date < end` and the portions sold."""
    sold = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.menu_item_id == MenuItem.id, Order.status.in_(SOLD))
        .scalar_subquery()
    )
    discounted = exists().where(
        Promotion.menu_item_id == MenuItem.id,
        Promotion.type == PromotionType.leftover,
        Promotion.approved_by.is_not(None),
    )
    query = (
        select(
            MenuItem.id,
            MenuItem.dish_id,
            Dish.category_id,
            MenuItem.menu_date,
            MenuItem.price,
            discounted,
            sold,
        )
        .join(Dish, Dish.id == MenuItem.dish_id)
        .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date < end)
        .order_by(MenuItem.menu_date, MenuItem.id)
    )
    if start is not None:
        query = query.where(MenuItem.menu_date >= start)
    frame = pd.DataFrame(db.execute(query).all(), columns=COLUMNS)
    frame["price"] = frame["price"].astype(float)
    frame["had_discount"] = frame["had_discount"].astype(int)
    frame["sold"] = frame["sold"].astype(int)
    return frame


class History:
    """Past sales by dish and day, for features and the baseline."""

    def __init__(self, sales: pd.DataFrame) -> None:
        self.by_day: dict[tuple[int, date], int] = {}
        self.days: dict[int, list[date]] = defaultdict(list)
        for dish_id, day, sold in sales[["dish_id", "menu_date", "sold"]].itertuples(index=False):
            self.by_day[(dish_id, day)] = self.by_day.get((dish_id, day), 0) + int(sold)
            self.days[dish_id].append(day)

    def mean(self, dish_id: int, days) -> float | None:
        values = [self.by_day[(dish_id, d)] for d in days if (dish_id, d) in self.by_day]
        return sum(values) / len(values) if values else None

    def recent_mean(self, dish_id: int, before: date, window: int = 28) -> float | None:
        start = before - timedelta(days=window)
        return self.mean(dish_id, [d for d in self.days.get(dish_id, []) if start <= d < before])

    def last_week(self, dish_id: int, day: date) -> float:
        week = [day - timedelta(days=i) for i in range(1, 8)]
        value = self.mean(dish_id, week)
        if value is None:
            value = self.recent_mean(dish_id, day)
        return value or 0.0

    def same_weekday(self, dish_id: int, day: date) -> float:
        value = self.mean(dish_id, [day - timedelta(weeks=i) for i in range(1, 5)])
        if value is None:
            value = self.recent_mean(dish_id, day)
        return value or 0.0


def features(frame: pd.DataFrame, history: History, ctx: Context) -> np.ndarray:
    """One row per menu item. `frame` holds whole days, so the category counts are right."""
    same_category = frame.groupby(["menu_date", "category_id"])["menu_item_id"].transform("count")
    rows = []
    for row, same in zip(frame.itertuples(index=False), same_category, strict=True):
        day: date = row.menu_date
        rows.append(
            [
                day.weekday(),
                max(0, (day - ctx.semester_start).days // 7 + 1),
                int(day in ctx.holidays),
                ctx.lessons.get(day.isoweekday(), 0),
                row.price,
                row.had_discount,
                same,
                history.last_week(row.dish_id, day),
                row.dish_id,
            ]
        )
    return np.array(rows, dtype=float).reshape(-1, len(FEATURES))


def predict_baseline(frame: pd.DataFrame, history: History) -> np.ndarray:
    return np.array(
        [history.same_weekday(r.dish_id, r.menu_date) for r in frame.itertuples(index=False)]
    )


def fit_gbm(train: pd.DataFrame, history: History, ctx: Context) -> GradientBoostingRegressor:
    # Shallow trees and the absolute-error loss: few rows, noisy days, and MAE is the metric.
    model = GradientBoostingRegressor(
        loss="absolute_error",
        n_estimators=400,
        max_depth=2,
        learning_rate=0.03,
        subsample=0.8,
        random_state=42,
    )
    model.fit(features(train, history, ctx), train["sold"].to_numpy(dtype=float))
    return model


def predict_both(
    train: pd.DataFrame, target: pd.DataFrame, history: History, ctx: Context
) -> dict[str, np.ndarray]:
    """Day-ahead predictions of both models for `target`; GBM only with enough history."""
    out = {BASELINE: predict_baseline(target, history)}
    if len(train) >= MIN_TRAIN_ROWS and len(target):
        model = fit_gbm(train, history, ctx)
        out[GBM] = np.clip(model.predict(features(target, history, ctx)), 0, None)
    return out


def backtest(sales: pd.DataFrame, ctx: Context, today: date) -> dict[str, dict]:
    """Train on everything before the last 2 weeks, forecast those 2 weeks, compare."""
    start = today - timedelta(days=BACKTEST_DAYS)
    train = sales[sales["menu_date"] < start]
    window = sales[(sales["menu_date"] >= start) & (sales["menu_date"] < today)]
    history = History(sales[sales["menu_date"] < today])
    predictions = predict_both(train, window, history, ctx)
    actual = window["sold"].tolist()
    return {name: metrics(actual, values.tolist()) for name, values in predictions.items()}


def choose(scores: dict[str, dict]) -> str:
    candidates = [name for name in MODELS if name in scores and scores[name]["n"] > 0]
    if not candidates:
        return BASELINE
    return min(candidates, key=lambda name: scores[name]["mae"])


def forecast_date(
    db: Session,
    canteen: Canteen,
    target: date,
    *,
    today: date | None = None,
    ctx: Context | None = None,
    backfill: bool = False,
    cache: dict | None = None,
) -> ForecastRun | None:
    """Forecast the menu of `target` with sales known before `today` (default: real today)."""
    today = today or clock.today_local()
    ctx = ctx or load_context(db)
    menu_items = db.scalars(
        select(MenuItem)
        .where(MenuItem.canteen_id == canteen.id, MenuItem.menu_date == target)
        .order_by(MenuItem.id)
    ).all()
    if not menu_items:
        return None
    key = (canteen.id, today)
    if cache is not None and key in cache:
        sales, scores = cache[key]
    else:
        sales = load_menu(db, canteen.id, None, today)
        scores = backtest(sales, ctx, today)
        if cache is not None:
            cache[key] = (sales, scores)
    model = choose(scores)
    target_frame = load_menu(db, canteen.id, target, target + timedelta(days=1))
    if target >= today:
        target_frame["had_discount"] = 0  # discounts are decided on the day itself
    predictions = predict_both(sales, target_frame, History(sales), ctx)
    model = model if model in predictions else BASELINE
    by_item = {int(mi_id): i for i, mi_id in enumerate(target_frame["menu_item_id"])}
    for mi in menu_items:
        mi.forecast_portions = int(round(float(predictions[model][by_item[mi.id]])))
        mi.forecast_model = model
    details = {
        "canteen_id": canteen.id,
        "history_until": (today - timedelta(days=1)).isoformat(),
        "train_rows": len(sales),
        "backtest": scores,
        "backfill": backfill,
        "predictions": {
            str(mi_id): {name: round(float(v[i]), 2) for name, v in predictions.items()}
            for mi_id, i in by_item.items()
        },
    }
    run = ForecastRun(
        target_date=target,
        model=model,
        mae=scores.get(model, {}).get("mae"),
        mape=scores.get(model, {}).get("mape"),
        details=details,
    )
    db.add(run)
    db.commit()
    return run


def forecast_upcoming(db: Session, horizon: int = HORIZON_DAYS) -> int:
    """Worker, every night: forecast each planned menu from today up to `horizon` days ahead."""
    today = clock.today_local()
    ctx = load_context(db)
    runs = 0
    cache: dict = {}
    canteens = db.scalars(select(Canteen).where(Canteen.is_active).order_by(Canteen.id)).all()
    for canteen in canteens:
        days = db.scalars(
            select(MenuItem.menu_date)
            .where(
                MenuItem.canteen_id == canteen.id,
                MenuItem.menu_date >= today,
                MenuItem.menu_date <= today + timedelta(days=horizon),
            )
            .distinct()
            .order_by(MenuItem.menu_date)
        ).all()
        for day in days:
            runs += forecast_date(db, canteen, day, today=today, ctx=ctx, cache=cache) is not None
    return runs


def has_runs(db: Session, canteen: Canteen) -> bool:
    return bool(
        db.scalar(
            select(func.count(ForecastRun.id)).where(
                ForecastRun.details["canteen_id"].as_integer() == canteen.id
            )
        )
    )


def backfill(db: Session, canteen: Canteen, days: int = BACKTEST_DAYS) -> int:
    """What the nightly job would have said on each of the last `days` days (for the report)."""
    today = clock.today_local()
    ctx = load_context(db)
    past = db.scalars(
        select(MenuItem.menu_date)
        .where(
            MenuItem.canteen_id == canteen.id,
            MenuItem.menu_date >= today - timedelta(days=days),
            MenuItem.menu_date < today,
        )
        .distinct()
        .order_by(MenuItem.menu_date)
    ).all()
    runs = 0
    for day in past:
        runs += forecast_date(db, canteen, day, today=day, ctx=ctx, backfill=True) is not None
    return runs


def prepare(db: Session, canteen: Canteen) -> None:
    """After the synthetic history: fill the report with past forecasts, then the future."""
    if not has_runs(db, canteen):
        log.info("forecast backfill for %s: %d days", canteen.slug, backfill(db, canteen))
    today = clock.today_local()
    ctx = load_context(db)
    cache: dict = {}
    for offset in range(HORIZON_DAYS + 1):
        forecast_date(
            db, canteen, today + timedelta(days=offset), today=today, ctx=ctx, cache=cache
        )


def prepare_active(db: Session) -> None:
    for canteen in db.scalars(
        select(Canteen)
        .where(Canteen.is_active, Canteen.synthetic_history_until.is_not(None))
        .order_by(Canteen.id)
    ).all():
        prepare(db, canteen)
