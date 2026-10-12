"""Charts for docs/load-test.md from a k6 CSV output (`k6 run --out csv=k6.csv ...`).

python infra/k6/report.py k6.csv docs/load-test

Writes <prefix>-latency.png (p50/p95 per 10 s and active VUs) and <prefix>-requests.png
(requests per second by answer: 2xx, 409, 5xx), and prints a per-endpoint table in Markdown.
Needs pandas and matplotlib (backend dev dependencies).
"""

import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BUCKET = 10  # seconds


def endpoint(row) -> str:
    path = re.sub(r"^https?://[^/]+/api/v1", "", row.url).split("?")[0]
    return f"{row.method} {re.sub(r'/\d+', '/{id}', path)}"


def main(csv: str, prefix: str) -> None:
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(csv, low_memory=False)
    start = data.timestamp.min()
    data["second"] = data.timestamp - start
    durations = data[data.metric_name == "http_req_duration"].copy()
    durations["endpoint"] = durations.apply(endpoint, axis=1)
    durations["bucket"] = durations.second // BUCKET * BUCKET
    vus = data[data.metric_name == "vus"].groupby("second").metric_value.max()

    table = (
        durations.groupby("endpoint")
        .metric_value.agg(
            requests="count",
            p50=lambda x: x.quantile(0.5),
            p95=lambda x: x.quantile(0.95),
            p99=lambda x: x.quantile(0.99),
            max="max",
        )
        .round(0)
        .astype(int)
    )
    print("| endpoint | requests | p50, ms | p95, ms | p99, ms | max, ms |")
    print("|---|---:|---:|---:|---:|---:|")
    for name, row in table.iterrows():
        print(f"| `{name}` | {row.requests} | {row.p50} | {row.p95} | {row.p99} | {row['max']} |")

    by_time = durations.groupby("bucket").metric_value
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(by_time.median().index, by_time.median(), label="p50")
    ax.plot(by_time.quantile(0.95).index, by_time.quantile(0.95), label="p95")
    ax.axhline(500, color="red", linestyle="--", linewidth=1, label="цель p95 = 500 мс")
    ax.set_xlabel("секунды от начала")
    ax.set_ylabel("время ответа, мс")
    right = ax.twinx()
    right.plot(vus.index, vus, color="gray", alpha=0.5, label="виртуальные студенты")
    right.set_ylabel("VU")
    lines = ax.get_legend_handles_labels()
    more = right.get_legend_handles_labels()
    ax.legend(lines[0] + more[0], lines[1] + more[1], loc="upper left")
    ax.set_title("Время ответа API под нагрузкой")
    fig.tight_layout()
    fig.savefig(f"{prefix}-latency.png", dpi=110)

    reqs = data[data.metric_name == "http_reqs"].copy()
    reqs["bucket"] = reqs.second // BUCKET * BUCKET
    reqs["answer"] = pd.cut(
        reqs.status, [0, 399, 409, 499, 599], labels=["2xx", "409", "4xx", "5xx"]
    ).astype(str)
    rate = reqs.groupby(["bucket", "answer"]).size().unstack(fill_value=0) / BUCKET
    fig, ax = plt.subplots(figsize=(9, 3.5))
    rate.plot.area(ax=ax, linewidth=0)
    ax.set_xlabel("секунды от начала")
    ax.set_ylabel("запросов в секунду")
    ax.set_title("Нагрузка: запросы в секунду по ответам")
    fig.tight_layout()
    fig.savefig(f"{prefix}-requests.png", dpi=110)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
