"""Forecast accuracy, without numpy, so the API can use it without loading the models."""

from collections.abc import Iterable


def metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float | int]:
    """MAE in portions and MAPE in percent (rows with no sales are left out of MAPE)."""
    pairs = [(float(a), float(p)) for a, p in zip(actual, predicted, strict=True)]
    if not pairs:
        return {"mae": 0.0, "mape": 0.0, "n": 0}
    mae = sum(abs(a - p) for a, p in pairs) / len(pairs)
    positive = [(a, p) for a, p in pairs if a > 0]
    mape = sum(abs(a - p) / a for a, p in positive) / len(positive) * 100 if positive else 0.0
    return {"mae": round(mae, 3), "mape": round(mape, 3), "n": len(pairs)}
