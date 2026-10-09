from __future__ import annotations

from typing import Any

# Metrics where an INCREASE is the regression, not a decrease — mirrors
# report.py's _RAW_VALUE_METRICS. Kept as a separate constant rather than
# importing report.py, since regression detection has nothing to do with
# report rendering and shouldn't depend on it.
_HIGHER_IS_WORSE_METRICS = {"latency_ms"}


def detect_regressions(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    threshold: float = 0.1,
    latency_relative_threshold: float = 0.2,
    latency_min_absolute_delta_ms: float = 5.0,
) -> list[dict[str, Any]]:
    """Match examples between two runs by their `input` text and flag
    per-metric regressions — this is what catches "one example completely
    broke" that an aggregate-average diff hides.

    For ordinary 0.0-1.0 metrics: a regression is a drop of more than
    `threshold` (absolute).
    For metrics in _HIGHER_IS_WORSE_METRICS (latency_ms): a regression
    needs BOTH a relative increase over `latency_relative_threshold` AND
    an absolute increase over `latency_min_absolute_delta_ms`. The
    absolute floor matters: a fast adapter's latency can jump from 2
    microseconds to 3 microseconds — a 50% relative "regression" that's
    actually just measurement noise, not a real slowdown. Without the
    floor, that's a false positive on every single run.

    Examples present in only one run are skipped (nothing to compare).
    Returns a flat list of regressions, each with input/metric/before/
    after/delta, most severe first within each metric.
    """
    def _key(row: dict[str, Any]) -> Any:
        return row.get("id") or row["input"]

    by_key_b = {_key(row): row for row in rows_b}

    regressions: list[dict[str, Any]] = []
    for row_a in rows_a:
        row_b = by_key_b.get(_key(row_a))
        if row_b is None:
            continue
        for metric, before in row_a["scores"].items():
            after = row_b["scores"].get(metric)
            if after is None:
                continue

            if metric in _HIGHER_IS_WORSE_METRICS:
                if before <= 0:
                    continue  # can't compute a meaningful percentage against a ~0 baseline
                absolute_delta = after - before
                relative_delta = absolute_delta / before
                is_regression = (
                    relative_delta > latency_relative_threshold
                    and absolute_delta > latency_min_absolute_delta_ms
                )
            else:
                is_regression = (after - before) < -threshold

            if is_regression:
                regressions.append(
                    {
                        "input": row_a["input"],
                        "metric": metric,
                        "before": before,
                        "after": after,
                        "delta": after - before,
                    }
                )

    def _severity(r: dict[str, Any]) -> float:
        # more negative delta = worse for normal metrics; more positive = worse for latency
        return r["delta"] if r["metric"] not in _HIGHER_IS_WORSE_METRICS else -r["delta"]

    regressions.sort(key=_severity)
    return regressions
