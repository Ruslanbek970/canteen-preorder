"""Forecast versus fact (SPEC 7.13, 8.8): what the nightly runs predicted and what was sold."""

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Dish, ForecastRun, MenuItem, Order, OrderItem
from app.schemas.reports import (
    ForecastDay,
    ForecastDish,
    ForecastReport,
    ForecastRunInfo,
    ForecastScore,
)
from app.services.reports import SOLD, _synthetic_until
from app.utils import time as clock
from ml.metrics import metrics

MODELS = ("baseline_avg", "gbm_v1")
UPCOMING = 8


def latest_runs(db: Session, canteen_id: int, start: date, end: date) -> dict[date, ForecastRun]:
    """The last run for each target day of the canteen in [start, end]."""
    runs = db.scalars(
        select(ForecastRun)
        .where(
            ForecastRun.details["canteen_id"].as_integer() == canteen_id,
            ForecastRun.target_date.between(start, end),
        )
        .order_by(ForecastRun.target_date, ForecastRun.run_at.desc(), ForecastRun.id.desc())
    ).all()
    latest: dict[date, ForecastRun] = {}
    for run in runs:
        latest.setdefault(run.target_date, run)
    return latest


def _scores(raw: dict | None) -> list[ForecastScore]:
    return [ForecastScore(model=name, **raw[name]) for name in MODELS if raw and name in raw]


def _sold(db: Session, canteen_id: int, start: date, end: date) -> dict[int, int]:
    rows = db.execute(
        select(OrderItem.menu_item_id, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .where(
            MenuItem.canteen_id == canteen_id,
            MenuItem.menu_date.between(start, end),
            Order.status.in_(SOLD),
        )
        .group_by(OrderItem.menu_item_id)
    ).all()
    return {mi_id: int(q) for mi_id, q in rows}


def forecast_rows(
    db: Session, canteen_id: int, start: date, end: date
) -> list[tuple[date, int, str, int, int, dict[str, float]]]:
    """(day, dish id, dish name, sold, served forecast, both models) for finished days."""
    end = min(end, clock.today_local() - date.resolution)
    if end < start:
        return []
    runs = latest_runs(db, canteen_id, start, end)
    sold = _sold(db, canteen_id, start, end)
    dishes = dict(
        db.execute(
            select(MenuItem.id, MenuItem.dish_id).where(
                MenuItem.canteen_id == canteen_id, MenuItem.menu_date.between(start, end)
            )
        ).all()
    )
    names = dict(db.execute(select(Dish.id, Dish.name_ru)).all())
    rows = []
    for day, run in sorted(runs.items()):
        for mi_id, predictions in (run.details or {}).get("predictions", {}).items():
            dish_id = dishes.get(int(mi_id))
            if dish_id is None:
                continue  # the dish was taken off the menu after the run
            served = round(predictions.get(run.model, predictions.get("baseline_avg", 0)))
            rows.append(
                (day, dish_id, names.get(dish_id, ""), sold.get(int(mi_id), 0), served, predictions)
            )
    return rows


def forecast_report(db: Session, canteen_id: int, start: date, end: date) -> ForecastReport:
    rows = forecast_rows(db, canteen_id, start, end)
    actual = [r[3] for r in rows]

    days: dict[date, dict] = {}
    for day, _dish, _name, sold, served, predictions in rows:
        d = days.setdefault(day, {"actual": 0, "forecast": 0, **{m: None for m in MODELS}})
        d["actual"] += sold
        d["forecast"] += served
        for name in MODELS:
            if name in predictions:
                d[name] = round((d[name] or 0) + predictions[name], 2)

    models = []
    for name in MODELS:
        pairs = [(r[3], r[5][name]) for r in rows if name in r[5]]
        if pairs:
            score = metrics([a for a, _ in pairs], [p for _, p in pairs])
            models.append(ForecastScore(model=name, **score))
    served = (
        ForecastScore(model="served", **metrics(actual, [r[4] for r in rows])) if rows else None
    )
    comparable = [m for m in models if m.n == len(rows)]
    better = min(comparable, key=lambda m: m.mae).model if len(comparable) == len(MODELS) else None

    per_dish: dict[int, dict] = defaultdict(lambda: {"actual": 0, "forecast": 0, "err": 0.0})
    for _day, dish_id, name, sold, served_value, _ in rows:
        item = per_dish[dish_id]
        item["name"] = name
        item["actual"] += sold
        item["forecast"] += served_value
        item["err"] += abs(sold - served_value)
        item["n"] = item.get("n", 0) + 1
    dishes = sorted(
        (
            ForecastDish(
                dish_id=dish_id,
                dish_name=v["name"],
                actual=v["actual"],
                forecast=v["forecast"],
                mae=round(v["err"] / v["n"], 2),
            )
            for dish_id, v in per_dish.items()
        ),
        key=lambda d: (-d.mae, d.dish_name),
    )

    today = clock.today_local()
    upcoming_runs = db.scalars(
        select(ForecastRun)
        .where(
            ForecastRun.details["canteen_id"].as_integer() == canteen_id,
            ForecastRun.target_date >= today,
        )
        .order_by(ForecastRun.target_date, ForecastRun.run_at.desc(), ForecastRun.id.desc())
    ).all()
    upcoming: dict[date, ForecastRunInfo] = {}
    for run in upcoming_runs:
        if run.target_date in upcoming or len(upcoming) >= UPCOMING:
            continue
        upcoming[run.target_date] = ForecastRunInfo(
            target_date=run.target_date,
            run_at=run.run_at,
            model=run.model,
            mae=float(run.mae) if run.mae is not None else None,
            mape=float(run.mape) if run.mape is not None else None,
            backtest=_scores((run.details or {}).get("backtest")),
        )

    return ForecastReport(
        from_date=start,
        to_date=end,
        synthetic_history_until=_synthetic_until(db, canteen_id),
        days=[ForecastDay(date=d, **v) for d, v in sorted(days.items())],
        models=models,
        served=served,
        better=better,
        dishes=dishes,
        upcoming=list(upcoming.values()),
    )
