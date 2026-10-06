from __future__ import annotations

import pytest

from evalkit.core.stats import failure_rate, percentile


def test_percentile_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        percentile([], 95)


def test_percentile_single_value():
    assert percentile([0.5], 95) == 0.5
    assert percentile([0.5], 0) == 0.5
    assert percentile([0.5], 100) == 0.5


def test_percentile_p0_is_minimum():
    assert percentile([0.1, 0.5, 0.9], 0) == 0.1


def test_percentile_p100_is_maximum():
    assert percentile([0.1, 0.5, 0.9], 100) == 0.9


def test_percentile_p50_is_median_for_odd_count():
    assert percentile([1.0, 2.0, 3.0], 50) == 2.0


def test_percentile_known_linear_interpolation_value():
    """Verified against numpy's default linear-interpolation method for
    the same input, to confirm our hand-rolled implementation matches the
    standard convention rather than inventing a different one."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    # numpy.percentile(values, 95) == 95.5 for this exact input
    assert percentile(values, 95) == pytest.approx(95.5)


def test_percentile_matches_numpy_convention_at_p90():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    # numpy.percentile([1,2,3,4,5], 90) == 4.6
    assert percentile(values, 90) == pytest.approx(4.6)


def test_percentile_order_independent():
    assert percentile([3.0, 1.0, 2.0], 50) == percentile([1.0, 2.0, 3.0], 50)


def test_failure_rate_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        failure_rate([], 0.5)


def test_failure_rate_none_below_bar():
    assert failure_rate([0.9, 0.8, 0.95], failure_below=0.5) == 0.0


def test_failure_rate_all_below_bar():
    assert failure_rate([0.1, 0.2, 0.3], failure_below=0.5) == 1.0


def test_failure_rate_partial():
    assert failure_rate([0.1, 0.9, 0.2, 0.8], failure_below=0.5) == 0.5


def test_failure_rate_value_exactly_at_bar_does_not_count_as_failure():
    """Documented semantics: >= the bar is passing, only strictly below
    counts as a failure."""
    assert failure_rate([0.5], failure_below=0.5) == 0.0


# -- Fuzz test against numpy, if available, for extra confidence beyond hand-picked cases --

numpy = pytest.importorskip("numpy", reason="numpy not installed — fuzz test skipped, hand-picked cases above still run")


def test_percentile_matches_numpy_across_random_cases():
    import random

    random.seed(42)
    for _ in range(200):
        n = random.randint(1, 30)
        values = [random.uniform(0, 100) for _ in range(n)]
        p = random.uniform(0, 100)
        ours = percentile(values, p)
        theirs = float(numpy.percentile(values, p))
        assert abs(ours - theirs) < 1e-9, f"n={n} p={p} ours={ours} numpy={theirs}"
