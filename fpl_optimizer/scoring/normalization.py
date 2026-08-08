"""Explainable feature normalization helpers."""

from __future__ import annotations

from collections import Counter


def percentile_scores(values: list[float]) -> list[float]:
    """Return tie-aware percentile ranks on a zero-to-100 scale."""

    if not values:
        return []
    if len(values) == 1 or min(values) == max(values):
        return [50.0 for _ in values]
    counts = Counter(values)
    lower_count: dict[float, int] = {}
    seen = 0
    for value in sorted(counts):
        lower_count[value] = seen
        seen += counts[value]
    denominator = len(values) - 1
    return [
        100.0 * (lower_count[value] + (counts[value] - 1) / 2) / denominator
        for value in values
    ]


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize non-negative raw weights to sum to one."""

    if any(value < 0 for value in weights.values()):
        raise ValueError("Strategy weights cannot be negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one strategy weight must be greater than zero")
    return {feature: value / total for feature, value in weights.items() if value > 0}
