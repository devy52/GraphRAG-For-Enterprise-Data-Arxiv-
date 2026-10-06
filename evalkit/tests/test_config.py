from __future__ import annotations

import textwrap

import pytest

from evalkit.core.config import EvalConfig


def test_from_yaml_loads_required_and_default_fields(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        textwrap.dedent(
            """
            track: rag
            dataset: data.jsonl
            adapter: static
            """
        )
    )
    config = EvalConfig.from_yaml(str(path))
    assert config.track == "rag"
    assert config.dataset == "data.jsonl"
    assert config.adapter == "static"
    # defaults
    assert config.judge_backend == "litellm"
    assert config.judge_model == "gpt-4o-mini"
    assert config.reporter == "markdown"
    assert config.output == "report.md"
    assert config.thresholds == []


def test_from_yaml_parses_thresholds_and_metrics(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        textwrap.dedent(
            """
            track: rag
            dataset: data.jsonl
            adapter: static
            metrics: [faithfulness, context_precision]
            thresholds:
              - metric: faithfulness
                min: 0.8
              - metric: context_precision
                min: 0.6
            """
        )
    )
    config = EvalConfig.from_yaml(str(path))
    assert config.metrics == ["faithfulness", "context_precision"]
    assert len(config.thresholds) == 2
    assert config.thresholds[0].metric == "faithfulness"
    assert config.thresholds[0].min == 0.8


def test_threshold_accepts_max_alone_for_lower_is_better_metrics(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        textwrap.dedent(
            """
            track: rag
            dataset: data.jsonl
            adapter: static
            thresholds:
              - metric: latency_ms
                max: 3000
            """
        )
    )
    config = EvalConfig.from_yaml(str(path))
    assert config.thresholds[0].min is None
    assert config.thresholds[0].max == 3000


def test_threshold_accepts_both_min_and_max(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        textwrap.dedent(
            """
            track: rag
            dataset: data.jsonl
            adapter: static
            thresholds:
              - metric: faithfulness
                min: 0.5
                max: 1.0
            """
        )
    )
    config = EvalConfig.from_yaml(str(path))
    assert config.thresholds[0].min == 0.5
    assert config.thresholds[0].max == 1.0


def test_threshold_with_neither_min_nor_max_raises():
    from evalkit.core.config import ThresholdConfig

    with pytest.raises(ValueError, match="sets no gate at all"):
        ThresholdConfig(metric="faithfulness")


def test_threshold_accepts_worst_case_gate_alone():
    from evalkit.core.config import ThresholdConfig

    t = ThresholdConfig(metric="faithfulness", worst_case_min=0.3)
    assert t.worst_case_min == 0.3
    assert t.min is None


def test_threshold_accepts_tail_gate_alone():
    from evalkit.core.config import ThresholdConfig

    t = ThresholdConfig(metric="latency_ms", tail_max=3000)
    assert t.tail_max == 3000


def test_threshold_max_failure_rate_requires_failure_below():
    from evalkit.core.config import ThresholdConfig

    with pytest.raises(ValueError, match="must be set together"):
        ThresholdConfig(metric="faithfulness", max_failure_rate=0.05)


def test_threshold_failure_below_alone_without_max_failure_rate_raises():
    """failure_below with no max_failure_rate isn't a gate at all — it's a
    dangling parameter with nothing to apply it to."""
    from evalkit.core.config import ThresholdConfig

    with pytest.raises(ValueError, match="must be set together"):
        ThresholdConfig(metric="faithfulness", failure_below=0.5)


def test_threshold_max_failure_rate_with_failure_below_is_valid():
    from evalkit.core.config import ThresholdConfig

    t = ThresholdConfig(metric="faithfulness", max_failure_rate=0.05, failure_below=0.5)
    assert t.max_failure_rate == 0.05
    assert t.failure_below == 0.5


def test_threshold_accepts_multiple_gate_types_simultaneously():
    from evalkit.core.config import ThresholdConfig

    t = ThresholdConfig(
        metric="faithfulness",
        min=0.85,
        worst_case_min=0.5,
        tail_min=0.7,
        max_failure_rate=0.05,
        failure_below=0.5,
    )
    assert t.min == 0.85
    assert t.worst_case_min == 0.5
    assert t.tail_min == 0.7


def test_from_yaml_handles_empty_file(tmp_path):
    """An empty config file shouldn't crash the YAML loader itself — it
    should surface as a normal pydantic validation error for missing
    required fields."""
    path = tmp_path / "config.yaml"
    path.write_text("")
    try:
        EvalConfig.from_yaml(str(path))
        assert False, "expected a validation error for missing required fields"
    except Exception as exc:
        assert "track" in str(exc) or "field required" in str(exc).lower()
