from __future__ import annotations

import pytest

from evalkit.core.regression import detect_regressions


def _row(input_text, **scores):
    return {"input": input_text, "output": "x", "reference": None, "context": None, "scores": scores}


def test_no_regression_when_scores_unchanged():
    rows_a = [_row("q1", faithfulness=0.9)]
    rows_b = [_row("q1", faithfulness=0.9)]
    assert detect_regressions(rows_a, rows_b) == []


def test_no_regression_when_score_improves():
    rows_a = [_row("q1", faithfulness=0.5)]
    rows_b = [_row("q1", faithfulness=0.9)]
    assert detect_regressions(rows_a, rows_b) == []


def test_regression_detected_when_score_drops_beyond_threshold():
    rows_a = [_row("q1", faithfulness=0.9)]
    rows_b = [_row("q1", faithfulness=0.3)]
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert len(regressions) == 1
    assert regressions[0]["metric"] == "faithfulness"
    assert regressions[0]["before"] == 0.9
    assert regressions[0]["after"] == 0.3
    assert regressions[0]["delta"] == pytest.approx(-0.6)


def test_no_regression_when_drop_is_within_threshold():
    rows_a = [_row("q1", faithfulness=0.9)]
    rows_b = [_row("q1", faithfulness=0.85)]  # only 0.05 drop, threshold is 0.1
    assert detect_regressions(rows_a, rows_b, threshold=0.1) == []


def test_this_is_the_actual_point_one_catastrophic_failure_hidden_by_averaging():
    """The exact scenario the review flagged: many examples slightly
    improve, one example completely breaks. An aggregate-mean diff can
    show this as a net positive. Per-example regression detection must
    still catch it."""
    rows_a = [_row(f"q{i}", faithfulness=0.7) for i in range(20)] + [_row("catastrophic", faithfulness=0.9)]
    rows_b = [_row(f"q{i}", faithfulness=0.8) for i in range(20)] + [_row("catastrophic", faithfulness=0.0)]

    # confirm the averaging trap is real: aggregate mean goes UP despite the collapse
    mean_a = sum(r["scores"]["faithfulness"] for r in rows_a) / len(rows_a)
    mean_b = sum(r["scores"]["faithfulness"] for r in rows_b) / len(rows_b)
    assert mean_b > mean_a

    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert len(regressions) == 1
    assert regressions[0]["input"] == "catastrophic"
    assert regressions[0]["after"] == 0.0


def test_examples_only_in_one_run_are_skipped_not_errored():
    rows_a = [_row("q1", faithfulness=0.9), _row("only-in-a", faithfulness=0.9)]
    rows_b = [_row("q1", faithfulness=0.2), _row("only-in-b", faithfulness=0.9)]
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert len(regressions) == 1
    assert regressions[0]["input"] == "q1"


def test_metric_only_in_one_run_is_skipped():
    rows_a = [_row("q1", faithfulness=0.9)]
    rows_b = [_row("q1", answer_relevancy=0.2)]  # different metric entirely
    assert detect_regressions(rows_a, rows_b) == []


def test_latency_regression_uses_relative_not_absolute_threshold():
    """latency_ms=100 -> 200 is a 100% relative increase, way over a 20%
    threshold, and 100ms absolute — well over the noise floor too."""
    rows_a = [_row("q1", latency_ms=100.0)]
    rows_b = [_row("q1", latency_ms=200.0)]
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1, latency_relative_threshold=0.2)
    assert len(regressions) == 1
    assert regressions[0]["metric"] == "latency_ms"


def test_latency_microsecond_noise_not_flagged_despite_large_relative_change():
    """The actual bug this floor fixes: a fast adapter's latency can jump
    from 2 microseconds to 3 microseconds — a 50% relative 'regression'
    that's pure measurement noise, not a real slowdown."""
    rows_a = [_row("q1", latency_ms=0.002)]
    rows_b = [_row("q1", latency_ms=0.003)]
    assert detect_regressions(rows_a, rows_b) == []


def test_latency_regression_at_noise_floor_boundary():
    """Just over the 5ms floor, with a relative change also over threshold
    -> must be flagged. Confirms the floor doesn't just silently disable
    latency regression detection wholesale."""
    rows_a = [_row("q1", latency_ms=10.0)]
    rows_b = [_row("q1", latency_ms=20.0)]  # +10ms absolute, 100% relative
    regressions = detect_regressions(rows_a, rows_b, latency_min_absolute_delta_ms=5.0)
    assert len(regressions) == 1


def test_latency_small_relative_increase_not_flagged():
    rows_a = [_row("q1", latency_ms=1000.0)]
    rows_b = [_row("q1", latency_ms=1050.0)]  # only 5% slower
    regressions = detect_regressions(rows_a, rows_b, latency_relative_threshold=0.2)
    assert regressions == []


def test_latency_decrease_is_not_a_regression():
    rows_a = [_row("q1", latency_ms=1000.0)]
    rows_b = [_row("q1", latency_ms=200.0)]  # much faster — an improvement
    assert detect_regressions(rows_a, rows_b) == []


def test_latency_zero_baseline_does_not_crash():
    rows_a = [_row("q1", latency_ms=0.0)]
    rows_b = [_row("q1", latency_ms=50.0)]
    # should not raise ZeroDivisionError, and shouldn't be flagged (can't compute a % from 0)
    assert detect_regressions(rows_a, rows_b) == []


def test_regressions_sorted_worst_first_for_normal_metrics():
    rows_a = [_row("q1", faithfulness=0.9), _row("q2", faithfulness=0.9)]
    rows_b = [_row("q1", faithfulness=0.5), _row("q2", faithfulness=0.1)]  # q2 dropped more
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert regressions[0]["input"] == "q2"  # worst (biggest drop) first
    assert regressions[1]["input"] == "q1"


def test_multiple_regressed_metrics_on_same_example():
    rows_a = [_row("q1", faithfulness=0.9, answer_relevancy=0.9)]
    rows_b = [_row("q1", faithfulness=0.2, answer_relevancy=0.3)]
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert len(regressions) == 2
    assert {r["metric"] for r in regressions} == {"faithfulness", "answer_relevancy"}


def test_regressions_distinguishes_identical_input_by_id():
    rows_a = [
        {"id": "id-1", "input": "identical query", "output": "x", "scores": {"faithfulness": 0.9}},
        {"id": "id-2", "input": "identical query", "output": "y", "scores": {"faithfulness": 0.9}},
    ]
    # id-1 drops, id-2 stays unchanged
    rows_b = [
        {"id": "id-1", "input": "identical query", "output": "x", "scores": {"faithfulness": 0.3}},
        {"id": "id-2", "input": "identical query", "output": "y", "scores": {"faithfulness": 0.9}},
    ]
    regressions = detect_regressions(rows_a, rows_b, threshold=0.1)
    assert len(regressions) == 1
    assert regressions[0]["input"] == "identical query"
    assert regressions[0]["before"] == 0.9
    assert regressions[0]["after"] == 0.3
