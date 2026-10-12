"""python -m ml.evaluate [--canteen main] [--days 28] [--out ../docs/ml]

Forecast-versus-fact for the diploma: a walk-forward test over the last `days` days. For
each day both models are trained only on the days before it (as the nightly job would be),
then compared with what was actually sold. Writes a CSV, a Markdown table and two charts.
Nothing is written to the database.
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Canteen, Dish
from app.utils import time as clock
from ml import forecast
from ml.metrics import metrics

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def walk_forward(sales: pd.DataFrame, ctx: forecast.Context, days: list[date]) -> pd.DataFrame:
    parts = []
    for day in days:
        before = sales[sales["menu_date"] < day]
        target = sales[sales["menu_date"] == day].copy()
        target["had_discount"] = 0
        predictions = forecast.predict_both(before, target, forecast.History(before), ctx)
        for name, values in predictions.items():
            target[name] = values
        parts.append(target)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def markdown(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *rows])


def summary(result: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in forecast.MODELS:
        if name in result:
            m = metrics(result["sold"], result[name])
            rows.append({"model": name, **m})
    return pd.DataFrame(rows)


def by_weekday(result: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for weekday, part in result.groupby(result["menu_date"].map(lambda d: d.weekday())):
        row = {"weekday": WEEKDAYS[weekday]}
        for name in forecast.MODELS:
            if name in part:
                row[f"{name}_mae"] = metrics(part["sold"], part[name])["mae"]
        rows.append(row)
    return pd.DataFrame(rows)


def charts(result: pd.DataFrame, names: dict[int, str], out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    daily = result.groupby("menu_date")[["sold", *forecast.MODELS]].sum()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(daily.index, daily["sold"], marker="o", color="#111827", label="Факт")
    ax.plot(daily.index, daily[forecast.BASELINE], linestyle="--", label="baseline_avg")
    ax.plot(daily.index, daily[forecast.GBM], label="gbm_v1")
    ax.set_title("Прогноз против факта: порций за день (синтетические данные)")
    ax.set_ylabel("порций")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    line = out / "forecast_vs_actual.png"
    fig.savefig(line, dpi=120)
    plt.close(fig)

    per_dish = (
        result.assign(
            baseline_err=(result["sold"] - result[forecast.BASELINE]).abs(),
            gbm_err=(result["sold"] - result[forecast.GBM]).abs(),
        )
        .groupby("dish_id")[["baseline_err", "gbm_err"]]
        .mean()
    )
    per_dish.index = [names.get(i, str(i)) for i in per_dish.index]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    per_dish.plot.bar(ax=ax, color=["#94a3b8", "#16a34a"])
    ax.set_title("MAE по блюдам, порций")
    ax.legend(["baseline_avg", "gbm_v1"])
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    bars = out / "mae_by_dish.png"
    fig.savefig(bars, dpi=120)
    plt.close(fig)
    return [line, bars]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canteen", default="main", help="canteen slug")
    parser.add_argument("--days", type=int, default=28, help="how many past days to test")
    parser.add_argument("--out", default="../docs/ml", help="where to put the results")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    today = clock.today_local()
    with SessionLocal() as db:
        canteen = db.scalar(select(Canteen).where(Canteen.slug == args.canteen))
        if canteen is None:
            raise SystemExit(f"no canteen {args.canteen!r}")
        ctx = forecast.load_context(db)
        sales = forecast.load_menu(db, canteen.id, None, today)
        names = dict(db.execute(select(Dish.id, Dish.name_ru)).all())
    start = today - timedelta(days=args.days)
    days = sorted(d for d in sales["menu_date"].unique() if d >= start)
    result = walk_forward(sales, ctx, days)
    if result.empty or forecast.GBM not in result:
        raise SystemExit("not enough history: run `make seed` first")

    result["dish"] = result["dish_id"].map(names)
    result[["menu_date", "dish", "sold", *forecast.MODELS]].round(2).to_csv(
        out / "forecast_vs_actual.csv", index=False
    )
    table = summary(result)
    weekdays = by_weekday(result)
    files = charts(result, names, out)
    better = table.sort_values("mae").iloc[0]["model"]
    report = [
        "# Прогноз против факта",
        "",
        f"Столовая `{args.canteen}`, дни {days[0]} — {days[-1]} ({len(days)} дней, "
        f"{len(result)} позиций меню). Данные синтетические (`ml/synthetic_history.py`).",
        "Каждый день модели обучены только на днях до него (walk-forward).",
        "",
        markdown(table),
        "",
        f"Точнее по MAE: **{better}**.",
        "",
        "## MAE по дням недели",
        "",
        markdown(weekdays),
        "",
        *[f"![{f.stem}]({f.name})" for f in files],
        "",
    ]
    (out / "results.md").write_text("\n".join(report), encoding="utf-8")
    print(table.to_string(index=False))
    print(f"better: {better}; files in {out}")


if __name__ == "__main__":
    main()
