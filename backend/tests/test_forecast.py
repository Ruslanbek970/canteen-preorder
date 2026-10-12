import random
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.models import ClassSchedule, ForecastRun, MenuItem, UserRole
from ml import forecast, synthetic_history
from ml.metrics import metrics
from worker import jobs

TODAY = date(2026, 10, 12)  # Monday
CTX = forecast.Context(semester_start=date(2026, 9, 1), holidays={date(2026, 10, 14)})


def frame(rows) -> pd.DataFrame:
    """rows: (menu_item_id, dish_id, category_id, day, sold)."""
    return pd.DataFrame(
        [(mi, dish, cat, day, 500.0, 0, sold) for mi, dish, cat, day, sold in rows],
        columns=forecast.COLUMNS,
    )


def test_metrics():
    assert metrics([10, 20, 0], [12, 15, 3]) == {"mae": 3.333, "mape": 22.5, "n": 3}
    assert metrics([], []) == {"mae": 0.0, "mape": 0.0, "n": 0}
    assert metrics([0], [2])["mape"] == 0.0


def test_baseline_is_the_same_weekday_mean_of_four_weeks():
    mondays = [TODAY - timedelta(weeks=i) for i in range(1, 6)]
    rows = [
        (i, 1, 1, d, sold)
        for i, (d, sold) in enumerate(zip(mondays, [10, 20, 30, 40, 99], strict=True))
    ]
    rows.append((50, 1, 1, TODAY - timedelta(days=3), 1000))  # a Friday: not used
    rows.append((51, 2, 1, TODAY - timedelta(days=3), 8))  # dish 2 only had a Friday
    history = forecast.History(frame(rows))
    target = frame([(100, 1, 1, TODAY, 0), (101, 2, 1, TODAY, 0), (102, 3, 1, TODAY, 0)])
    assert forecast.predict_baseline(target, history).tolist() == [25.0, 8.0, 0.0]


def test_features():
    history = forecast.History(
        frame([(1, 1, 1, date(2026, 10, 12) - timedelta(days=d), 10 * d) for d in (1, 2, 8)])
    )
    target = frame(
        [
            (10, 1, 1, date(2026, 10, 14), 0),
            (11, 2, 1, date(2026, 10, 14), 0),
            (12, 3, 2, date(2026, 10, 14), 0),
        ]
    )
    ctx = forecast.Context(CTX.semester_start, CTX.holidays, {3: 42})
    x = forecast.features(target, history, ctx)
    named = dict(zip(forecast.FEATURES, x[0], strict=True))
    assert named == {
        "weekday": 2,
        "semester_week": 7,
        "holiday": 1,
        "lessons": 42,
        "price": 500,
        "had_discount": 0,
        "same_category": 2,
        "last_week_sales": 15,  # days 10-11 and 10-10 had 10 and 20, 10-04 is too old
        "dish_id": 1,
    }
    assert x[2][6] == 1  # the only dish of its category


def _synthetic_sales(weeks: int = 10, seed: int = 1) -> pd.DataFrame:
    """Two dishes with a weekday pattern and a 15% noise, like the demo history."""
    rng = random.Random(seed)
    factor = {0: 1.0, 1: 1.1, 2: 1.15, 3: 1.0, 4: 0.75}
    rows, mi = [], 0
    start = TODAY - timedelta(weeks=weeks)
    for offset in range((TODAY - start).days):
        day = start + timedelta(days=offset)
        if day.weekday() > 4:
            continue
        for dish, base in ((1, 80), (2, 30)):
            mi += 1
            rows.append(
                (mi, dish, 1, day, round(base * factor[day.weekday()] * rng.gauss(1, 0.15)))
            )
    return frame(rows)


def test_backtest_prefers_the_more_accurate_model():
    sales = _synthetic_sales()
    scores = forecast.backtest(sales, CTX, TODAY)
    assert set(scores) == {"baseline_avg", "gbm_v1"}
    assert scores["baseline_avg"]["n"] == scores["gbm_v1"]["n"] == 20  # 10 days x 2 dishes
    better = min(scores, key=lambda name: scores[name]["mae"])
    assert forecast.choose(scores) == better
    assert forecast.choose({"baseline_avg": {"mae": 1, "n": 5}, "gbm_v1": {"mae": 2, "n": 5}}) == (
        "baseline_avg"
    )
    assert forecast.choose({}) == "baseline_avg"


def test_too_little_history_means_baseline_only():
    sales = _synthetic_sales(weeks=3)
    assert set(forecast.backtest(sales, CTX, TODAY)) == {"baseline_avg"}


@pytest.fixture
def history(db, factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen(slug="main")
    factory.user(UserRole.cook, canteen=canteen)
    for name in ("Плов", "Самса"):
        factory.dish(name_ru=name, price=600, shelf_life_hours=6)
    group = factory.group()
    for day in range(1, 6):
        factory.lesson(group, day, "09:00", "10:20")
    synthetic_history.generate(db, canteen, weeks=7)
    dishes = db.scalars(select(MenuItem.dish_id).distinct()).all()
    for offset in (0, 1):
        for dish_id in dishes:
            db.add(
                MenuItem(
                    canteen_id=canteen.id,
                    dish_id=dish_id,
                    menu_date=TODAY + timedelta(days=offset),
                    price=600,
                    planned_portions=50,
                    available_portions=50,
                )
            )
    db.commit()
    return canteen


def test_forecast_date_writes_menu_and_run(db, history):
    run = forecast.forecast_date(db, history, TODAY + timedelta(days=1))
    assert run.model in forecast.MODELS
    assert set(run.details["backtest"]) == {"baseline_avg", "gbm_v1"}
    assert float(run.mae) == run.details["backtest"][run.model]["mae"]
    items = db.scalars(
        select(MenuItem).where(MenuItem.menu_date == TODAY + timedelta(days=1))
    ).all()
    assert all(mi.forecast_model == run.model and mi.forecast_portions > 0 for mi in items)
    assert set(run.details["predictions"]) == {str(mi.id) for mi in items}
    assert forecast.forecast_date(db, history, TODAY + timedelta(days=5)) is None  # no menu


def test_nightly_job_and_report(client, auth, db, factory, history):
    assert forecast.backfill(db, history, days=7) == 5  # five past weekdays
    assert jobs.forecast_tomorrow() == 2  # today and tomorrow have a menu
    assert db.scalar(select(func.count(ForecastRun.id))) == 7

    manager = factory.user(UserRole.canteen_manager, canteen=history)
    h = auth(manager)
    report = client.get(
        "/api/v1/manager/reports/forecast?from=2026-10-01&to=2026-10-12", headers=h
    ).json()
    assert [d["date"] for d in report["days"]] == [
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
        "2026-10-08",
        "2026-10-09",
    ]
    assert {m["model"] for m in report["models"]} == {"baseline_avg", "gbm_v1"}
    assert report["better"] in forecast.MODELS
    assert report["served"]["n"] == sum(len(d) for d in [report["dishes"]]) * 5
    day = report["days"][0]
    assert day["actual"] > 0 and day["forecast"] > 0
    assert [u["target_date"] for u in report["upcoming"]] == ["2026-10-12", "2026-10-13"]
    assert report["synthetic_history_until"] == "2026-10-09"

    csv = client.get(
        "/api/v1/manager/reports/forecast.csv?from=2026-10-01&to=2026-10-12", headers=h
    )
    lines = csv.text.lstrip("﻿").splitlines()
    assert lines[0] == "date,dish,actual,forecast,baseline_avg,gbm_v1"
    assert len(lines) == 1 + report["served"]["n"]

    other = auth(factory.user(UserRole.canteen_manager))
    assert client.get("/api/v1/manager/reports/forecast", headers=other).json()["days"] == []
    student = auth(factory.user())
    assert client.get("/api/v1/manager/reports/forecast", headers=student).status_code == 403


def test_lessons_come_from_the_timetable(db, factory):
    group = factory.group()
    factory.lesson(group, 1, "09:00", "10:20")
    factory.lesson(group, 1, "10:30", "11:50")
    factory.lesson(group, 3, "09:00", "10:20")
    assert forecast.load_context(db).lessons == {1: 2, 3: 1}
    assert db.scalar(select(func.count(ClassSchedule.id))) == 3


def test_evaluate_walk_forward_and_files(tmp_path):
    from ml import evaluate

    sales = _synthetic_sales(weeks=8)
    days = sorted(d for d in sales["menu_date"].unique() if d >= TODAY - timedelta(days=7))
    result = evaluate.walk_forward(sales, CTX, days)
    assert len(result) == 10 and {"baseline_avg", "gbm_v1"} <= set(result.columns)
    table = evaluate.summary(result)
    assert list(table["model"]) == ["baseline_avg", "gbm_v1"]
    assert evaluate.markdown(table).splitlines()[0] == "| model | mae | mape | n |"
    assert list(evaluate.by_weekday(result)["weekday"]) == ["Пн", "Вт", "Ср", "Чт", "Пт"]
    files = evaluate.charts(result, {1: "Плов", 2: "Самса"}, tmp_path)
    assert all(f.stat().st_size > 1000 for f in files)
