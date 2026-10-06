from __future__ import annotations


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile — same convention as numpy's default
    'linear' method, implemented without a numpy dependency. p is 0-100
    (e.g. 95 for p95).
    """
    if not values:
        raise ValueError("cannot compute a percentile of an empty list")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (p / 100) * (len(sorted_values) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    return sorted_values[lower_index] + fraction * (sorted_values[upper_index] - sorted_values[lower_index])


def failure_rate(values: list[float], failure_below: float) -> float:
    """Fraction of values strictly below `failure_below`. A value exactly
    equal to the bar counts as passing, not failing — consistent with
    typical 'score >= bar' pass semantics."""
    if not values:
        raise ValueError("cannot compute a failure rate of an empty list")
    failures = sum(1 for v in values if v < failure_below)
    return failures / len(values)
