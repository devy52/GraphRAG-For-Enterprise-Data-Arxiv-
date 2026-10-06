import json
import sys
import textwrap

import pytest

import evalkit  # noqa: F401  (triggers built-in registration)
from evalkit.core.config import EvalConfig
from evalkit.core.runner import Runner


def _write_dataset(tmp_path):
    path = tmp_path / "data.jsonl"
    rows = [
        {"input": "What is 2+2?", "reference": "4", "metadata": {"precomputed_output": "4"}},
        {"input": "Capital of France?", "reference": "Paris", "metadata": {"precomputed_output": "Paris"}},
    ]
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return str(path)


def test_end_to_end_generic_track(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
    )
    result = Runner(config).run()

    assert len(result.per_example) == 2
    assert all("quality" in row["scores"] for row in result.per_example)

    agg = result.aggregate()
    assert "quality" in agg
    assert 0.0 <= agg["quality"] <= 1.0


def test_end_to_end_rag_track(tmp_path):
    path = tmp_path / "rag_data.jsonl"
    with open(path, "w") as f:
        f.write(
            json.dumps(
                {
                    "input": "When was the tower built?",
                    "context": ["The tower was completed in 1889."],
                    "metadata": {"precomputed_output": "It was completed in 1889."},
                }
            )
            + "\n"
        )

    config = EvalConfig(
        track="rag",
        dataset=str(path),
        adapter="static",
        metrics=["faithfulness"],
        judge_backend="dummy",
        judge_model="dummy",
    )
    result = Runner(config).run()
    assert "faithfulness" in result.per_example[0]["scores"]


def test_threshold_failure_is_reported(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        thresholds=[{"metric": "quality", "min": 999.0}],  # impossible to pass
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "quality" in failures[0]


def test_threshold_on_never_computed_metric_reports_clear_message(tmp_path):
    """A threshold typo'd or referencing a metric this track doesn't
    produce must show up as a clear failure message, not a KeyError or a
    silent pass."""
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        thresholds=[{"metric": "faithfulness", "min": 0.8}],  # generic track never computes this
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "no scores reported" in failures[0]


def test_max_threshold_fails_when_value_too_high(tmp_path):
    """max is for lower-is-better metrics like latency_ms — must fail when
    the average EXCEEDS max, not when it's below (that's what min is for)."""
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        thresholds=[{"metric": "latency_ms", "max": 0.0}],  # any real latency exceeds 0ms
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "> 0.0" in failures[0] or "maximum" in failures[0]


def test_max_threshold_passes_when_value_is_low_enough(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        thresholds=[{"metric": "latency_ms", "max": 60000}],  # generous, a static adapter is fast
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_combined_min_and_max_threshold(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
        thresholds=[{"metric": "quality", "min": 0.0, "max": 1.0}],  # dummy judge always in [0,1)
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


# -- Caching integration ----------------------------------------------------


def test_cache_disabled_by_default_config_still_populates_when_true(tmp_path):
    """cache: true (the default) — a second Runner.run() with a fresh judge
    instance must reuse cached scores instead of recomputing, end to end
    through the real Runner, not just the CachingJudgeBackend unit."""
    from unittest.mock import patch

    dataset_path = tmp_path / "data.jsonl"
    dataset_path.write_text(json.dumps({"input": "q", "metadata": {"precomputed_output": "a"}}) + "\n")
    cache_dir = str(tmp_path / "cache")

    config = EvalConfig(
        track="generic",
        dataset=str(dataset_path),
        adapter="static",
        metrics=["quality"],
        judge_backend="litellm",
        judge_model="gpt-4o-mini",
        cache=True,
        cache_dir=cache_dir,
    )

    fake_response = {"choices": [{"message": {"content": "0.77"}}]}
    with patch("litellm.completion", return_value=fake_response) as mock_completion:
        Runner(config).run()
        Runner(config).run()  # second Runner instance, same cache_dir

    # litellm.completion should have been called only once total across both runs
    assert mock_completion.call_count == 1


def test_cache_false_never_reuses_across_runs(tmp_path):
    from unittest.mock import patch

    dataset_path = tmp_path / "data.jsonl"
    dataset_path.write_text(json.dumps({"input": "q", "metadata": {"precomputed_output": "a"}}) + "\n")

    config = EvalConfig(
        track="generic",
        dataset=str(dataset_path),
        adapter="static",
        metrics=["quality"],
        judge_backend="litellm",
        judge_model="gpt-4o-mini",
        cache=False,
    )

    fake_response = {"choices": [{"message": {"content": "0.5"}}]}
    with patch("litellm.completion", return_value=fake_response) as mock_completion:
        Runner(config).run()
        Runner(config).run()

    assert mock_completion.call_count == 2


def test_cache_stats_reported_on_result(tmp_path):
    dataset_path = tmp_path / "data.jsonl"
    dataset_path.write_text(json.dumps({"input": "q", "metadata": {"precomputed_output": "a"}}) + "\n")

    config = EvalConfig(
        track="generic",
        dataset=str(dataset_path),
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        cache=True,
        cache_dir=str(tmp_path / "cache"),
    )
    result = Runner(config).run()
    assert result.cache_stats is not None
    assert result.cache_stats["hits"] == 0
    assert result.cache_stats["misses"] == 1


def test_cache_stats_none_when_cache_disabled(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        cache=False,
    )
    result = Runner(config).run()
    assert result.cache_stats is None


# -- Concurrency --------------------------------------------------------------


def test_concurrent_execution_produces_same_results_as_sequential(tmp_path):
    """max_concurrency > 1 must not change *what* gets computed — same
    scores, same order — only how fast it happens."""
    dataset_path = tmp_path / "data.jsonl"
    with open(dataset_path, "w") as f:
        for i in range(8):
            f.write(json.dumps({"input": f"question {i}", "metadata": {"precomputed_output": f"answer {i}"}}) + "\n")

    base_kwargs = dict(
        track="generic",
        dataset=str(dataset_path),
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        cache=False,
    )
    sequential = Runner(EvalConfig(max_concurrency=1, **base_kwargs)).run()
    concurrent = Runner(EvalConfig(max_concurrency=4, **base_kwargs)).run()

    seq_inputs = [r["input"] for r in sequential.per_example]
    con_inputs = [r["input"] for r in concurrent.per_example]
    assert seq_inputs == con_inputs  # order preserved despite parallel execution

    for seq_row, con_row in zip(sequential.per_example, concurrent.per_example):
        assert seq_row["scores"]["quality"] == con_row["scores"]["quality"]


def test_concurrent_execution_actually_overlaps_in_time(tmp_path):
    """Not just 'doesn't crash' — actually verifies parallelism happened,
    by using an adapter with an artificial delay and checking total wall
    time is well under what N sequential delays would take."""
    import time

    from evalkit.contracts.adapter import BaseAdapter

    slow_dir = tmp_path / "slow_pkg"
    slow_dir.mkdir()
    (slow_dir / "slow_adapter.py").write_text(
        "import time\n"
        "from evalkit.contracts.adapter import BaseAdapter\n\n"
        "class SlowAdapter(BaseAdapter):\n"
        "    def run(self, example_input, metadata=None):\n"
        "        time.sleep(0.1)\n"
        "        return 'done'\n"
    )
    import sys

    sys.path.insert(0, str(slow_dir))
    try:
        dataset_path = tmp_path / "data.jsonl"
        with open(dataset_path, "w") as f:
            for i in range(6):
                f.write(json.dumps({"input": f"q{i}"}) + "\n")

        config = EvalConfig(
            track="generic",
            dataset=str(dataset_path),
            adapter="slow_adapter:SlowAdapter",
            metrics=["quality"],
            judge_backend="dummy",
            judge_model="dummy",
            cache=False,
            max_concurrency=6,
        )
        start = time.monotonic()
        Runner(config).run()
        elapsed = time.monotonic() - start

        # 6 examples * 100ms sequentially would be >= 600ms; concurrent
        # with max_concurrency=6 should finish in roughly one delay's worth
        assert elapsed < 0.4
    finally:
        sys.path.remove(str(slow_dir))


def test_max_concurrency_one_is_still_default_and_unchanged_behavior(tmp_path):
    """Backward-compat guard: omitting max_concurrency must behave exactly
    like the pre-concurrency implementation — sequential, no thread pool."""
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        metrics=["quality"],
        judge_backend="dummy",
        judge_model="dummy",
        cache=False,
    )
    assert config.max_concurrency == 1
    result = Runner(config).run()
    assert len(result.per_example) == 2


# -- Multi-level CI gates -----------------------------------------------------


def _dataset_with_scores(tmp_path, scores: list[float]):
    """Build a text_similarity dataset where each example's exact_match
    score is deterministically controllable — 1.0 if output==reference,
    0.0 otherwise — so we can construct exact score distributions to test
    percentile/worst-case/failure-rate gates against."""
    path = tmp_path / "data.jsonl"
    with open(path, "w") as f:
        for i, want_pass in enumerate(scores):
            output = "correct" if want_pass == 1.0 else "wrong"
            f.write(
                json.dumps(
                    {
                        "input": f"q{i}",
                        "reference": "correct",
                        "metadata": {"precomputed_output": output},
                    }
                )
                + "\n"
            )
    return str(path)


def test_worst_case_min_catches_single_outlier_hidden_by_good_mean(tmp_path):
    """The exact scenario multi-level gating exists for: mean easily
    passes a min: 0.5 gate, but one example is a total failure that
    worst_case_min catches and mean-only gating would miss entirely."""
    scores = [1.0] * 9 + [0.0]  # mean = 0.9, comfortably above 0.5
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "min": 0.5, "worst_case_min": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()

    assert len(failures) == 1  # min: 0.5 passes (mean=0.9), worst_case_min: 0.5 fails
    assert "worst_case_min" in failures[0]
    assert "worst-case" in failures[0]


def test_worst_case_passes_when_no_outlier(tmp_path):
    scores = [1.0] * 10
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "worst_case_min": 0.5}],
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_worst_case_max_catches_a_single_outlier_going_too_high(tmp_path):
    """worst_case_max is the mirror of worst_case_min — for a
    'lower is better' style metric, not even one example may exceed the
    bound, regardless of how good the rest look."""
    scores = [0.0] * 9 + [1.0]  # mean is low (0.1), but one value spikes to 1.0
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "worst_case_max": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "worst_case_max" in failures[0]


def test_worst_case_max_passes_when_nothing_exceeds_bound(tmp_path):
    scores = [0.0] * 10
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "worst_case_max": 0.5}],
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_tail_min_catches_bad_tail_that_worst_case_would_also_catch(tmp_path):
    """10% failing (2 of 20) at the bottom of the distribution -> the 5th
    percentile (default tail_percentile) sits right in that failing
    region, correctly pulled down to 0.0."""
    scores = [1.0] * 18 + [0.0] * 2
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_min": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "tail_min" in failures[0]


def test_tail_min_passes_when_bottom_tail_is_clean(tmp_path):
    scores = [1.0] * 20
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_min": 0.5}],
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_tail_min_single_outlier_out_of_twenty_is_too_small_to_move_p5_much(tmp_path):
    """Documents the real limit found while building this: a single
    failure out of 20 only pulls p5 down to 0.95 (still passes a lenient
    0.5 bound) — tail gates need a genuinely sized bad fraction to fire,
    unlike worst_case_min which catches a single outlier unconditionally.
    This is why worst_case_min exists as a separate, stricter gate."""
    scores = [1.0] * 19 + [0.0]
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_min": 0.5, "worst_case_min": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1  # only worst_case_min fires; tail_min (p5=0.95) still passes
    assert "worst_case_min" in failures[0]


def test_tail_max_catches_bad_tail_at_the_top_of_the_distribution(tmp_path):
    """tail_max checks the OPPOSITE end from tail_min — the top
    tail_percentile% must not exceed the bound. Verified mechanically here
    (metric-agnostic gate; real usage is latency_ms where high = bad)."""
    scores = [0.0] * 18 + [1.0] * 2  # "bad" (high) values clustered at the top
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_max": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "tail_max" in failures[0]


def test_tail_max_passes_when_top_tail_is_clean(tmp_path):
    scores = [0.0] * 20
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_max": 0.5}],
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_tail_percentile_is_configurable(tmp_path):
    """tail_percentile controls how far into the tail the gate looks. A
    SMALLER tail_percentile is MORE sensitive (the percentile point sits
    right at the edge of even a small bad fraction); a LARGER one is more
    lenient (it reaches further into the bulk of the distribution, so it
    takes a bigger bad fraction to pull the percentile point down at
    all)."""
    scores = [1.0] * 90 + [0.0] * 10  # 100 examples, 10% failing
    dataset_path = _dataset_with_scores(tmp_path, scores)

    config_narrow = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_min": 0.9}],  # default tail_percentile=5
    )
    config_wide = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "tail_min": 0.9, "tail_percentile": 20.0}],
    )
    # the default 5% tail sits entirely within the 10% bad region -> catches it
    assert len(Runner(config_narrow).run().failed_thresholds()) == 1
    # widening to 20% reaches past the bad region into the good bulk -> misses it
    assert Runner(config_wide).run().failed_thresholds() == []


def test_max_failure_rate_gate(tmp_path):
    scores = [1.0] * 8 + [0.0] * 2  # 20% failure rate
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "max_failure_rate": 0.1, "failure_below": 0.5}],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 1
    assert "failure rate" in failures[0]
    assert "20.0%" in failures[0]


def test_max_failure_rate_gate_passes_under_bar(tmp_path):
    scores = [1.0] * 19 + [0.0] * 1  # 5% failure rate
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[{"metric": "exact_match", "max_failure_rate": 0.1, "failure_below": 0.5}],
    )
    result = Runner(config).run()
    assert result.failed_thresholds() == []


def test_multiple_gate_types_on_same_metric_can_each_independently_fail(tmp_path):
    """mean, worst-case, and failure-rate gates on the SAME metric are
    independent checks — a run can fail more than one simultaneously, and
    each failure should be reported separately, not merged into one."""
    scores = [0.3] * 10  # mean=0.3, worst=0.3, failure_rate=100% (all below 0.5)
    dataset_path = _dataset_with_scores(tmp_path, scores)
    config = EvalConfig(
        track="text_similarity",
        dataset=dataset_path,
        adapter="static",
        metrics=["exact_match"],
        cache=False,
        thresholds=[
            {
                "metric": "exact_match",
                "min": 0.8,
                "worst_case_min": 0.8,
                "max_failure_rate": 0.1,
                "failure_below": 0.5,
            }
        ],
    )
    result = Runner(config).run()
    failures = result.failed_thresholds()
    assert len(failures) == 3  # min, worst_case_min, and max_failure_rate all fail


def test_multi_track_merges_scores_with_prefixed_keys(tmp_path):
    """track as a list runs every listed evaluator and merges their scores
    into one report — this is the 'every metric possible' mode. Keys must
    be prefixed with the track name so two evaluators computing the same
    metric name never collide."""
    path = tmp_path / "rag_data.jsonl"
    with open(path, "w") as f:
        f.write(
            json.dumps(
                {
                    "input": "When was it built?",
                    "context": ["Completed in 1889."],
                    "metadata": {"precomputed_output": "It was completed in 1889."},
                }
            )
            + "\n"
        )

    config = EvalConfig(
        track=["rag", "generic"],
        dataset=str(path),
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
    )
    result = Runner(config).run()
    scores = result.per_example[0]["scores"]

    assert "rag.faithfulness" in scores
    assert "rag.context_precision" in scores
    assert "rag.answer_relevancy" in scores
    assert "generic.quality" in scores
    # unprefixed keys must NOT appear in multi-track mode
    assert "faithfulness" not in scores
    assert "quality" not in scores


def test_single_track_still_unprefixed_after_multi_track_support_added(tmp_path):
    """Regression guard: track as a plain string must keep producing
    unprefixed keys exactly as before — multi-track is opt-in via list."""
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
    )
    result = Runner(config).run()
    assert "quality" in result.per_example[0]["scores"]
    assert "generic.quality" not in result.per_example[0]["scores"]


def test_multi_track_reserved_evaluator_config_keys_raise_clear_error(tmp_path):
    """evaluator_config accidentally setting 'metrics' or 'judge' (already
    top-level config fields) must fail with a clear message, not a
    confusing TypeError about duplicate keyword arguments."""
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"input": "q", "metadata": {"precomputed_output": "a"}}) + "\n")

    config = EvalConfig(
        track=["generic"],
        dataset=str(path),
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
        evaluator_config={"generic": {"metrics": ["quality"]}},
    )
    with pytest.raises(ValueError, match="evaluator_config"):
        Runner(config).run()


def test_multi_track_respects_per_track_evaluator_config(tmp_path):
    """Nested evaluator_config ({"track_name": {...}}) must route only to
    that track's evaluator and not leak into others, which would raise if
    they don't accept the same kwargs."""
    custom_module_dir = tmp_path / "custom_pkg"
    custom_module_dir.mkdir()
    (custom_module_dir / "weighted_eval.py").write_text(
        textwrap.dedent(
            """
            from evalkit.contracts.evaluator import BaseEvaluator

            class WeightedEvaluator(BaseEvaluator):
                def __init__(self, judge=None, metrics=None, weight=1.0):
                    self.weight = weight

                def evaluate(self, example_input, output, reference, context, metadata):
                    return {"weighted": 1.0 * self.weight}
            """
        )
    )
    sys.path.insert(0, str(custom_module_dir))
    try:
        dataset_path = tmp_path / "data.jsonl"
        dataset_path.write_text(json.dumps({"input": "q", "metadata": {"precomputed_output": "a"}}) + "\n")

        config = EvalConfig(
            track=["generic", "weighted_eval:WeightedEvaluator"],
            dataset=str(dataset_path),
            adapter="static",
            judge_backend="dummy",
            judge_model="dummy",
            # only the custom track gets its extra kwarg; "generic" gets none
            # and must NOT receive "weight" (it doesn't accept it, would raise)
            evaluator_config={"weighted_eval:WeightedEvaluator": {"weight": 3.0}},
        )
        result = Runner(config).run()
        scores = result.per_example[0]["scores"]
        assert scores["weighted_eval:WeightedEvaluator.weighted"] == 3.0
        assert "generic.quality" in scores
    finally:
        sys.path.remove(str(custom_module_dir))


def test_multi_track_all_metrics_default_applies_per_evaluator(tmp_path):
    """metrics: [] (the default) means 'every metric this evaluator
    supports' — in multi-track mode that must apply independently to each
    evaluator, not just the first one."""
    path = tmp_path / "rag_data.jsonl"
    with open(path, "w") as f:
        f.write(
            json.dumps(
                {"input": "q", "context": ["ctx"], "metadata": {"precomputed_output": "a"}}
            )
            + "\n"
        )
    config = EvalConfig(
        track=["rag", "generic"],
        dataset=str(path),
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
        # metrics deliberately left empty
    )
    result = Runner(config).run()
    scores = result.per_example[0]["scores"]
    # rag's full metric set, not just one
    assert {"rag.faithfulness", "rag.context_precision", "rag.answer_relevancy"} <= scores.keys()
    assert "generic.quality" in scores


def test_latency_ms_always_present_and_reasonable(tmp_path):
    """latency_ms is measured for every example regardless of track config —
    it's about the adapter call, not any particular evaluator."""
    dataset_path = _write_dataset(tmp_path)
    config = EvalConfig(
        track="generic",
        dataset=dataset_path,
        adapter="static",
        judge_backend="dummy",
        judge_model="dummy",
    )
    result = Runner(config).run()
    for row in result.per_example:
        assert "latency_ms" in row["scores"]
        assert row["scores"]["latency_ms"] >= 0.0


def test_latency_ms_reflects_actual_adapter_delay(tmp_path):
    """Not just present — actually measuring something real. A slow adapter
    must show up as a larger latency_ms than a fast one."""
    import time

    from evalkit.contracts.adapter import BaseAdapter

    slow_module_dir = tmp_path / "slow_pkg"
    slow_module_dir.mkdir()
    (slow_module_dir / "slow_adapter.py").write_text(
        "import time\n"
        "from evalkit.contracts.adapter import BaseAdapter\n\n"
        "class SlowAdapter(BaseAdapter):\n"
        "    def run(self, example_input, metadata=None):\n"
        "        time.sleep(0.05)\n"
        "        return 'done'\n"
    )
    sys.path.insert(0, str(slow_module_dir))
    try:
        dataset_path = tmp_path / "data.jsonl"
        dataset_path.write_text(json.dumps({"input": "q"}) + "\n")
        config = EvalConfig(
            track="generic",
            dataset=str(dataset_path),
            adapter="slow_adapter:SlowAdapter",
            metrics=["quality"],
            judge_backend="dummy",
            judge_model="dummy",
        )
        result = Runner(config).run()
        assert result.per_example[0]["scores"]["latency_ms"] >= 45  # slept 50ms, allow scheduling slack
    finally:
        sys.path.remove(str(slow_module_dir))
