from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import evalkit.evaluators.ragas_backed as ragas_backed_module
from evalkit.evaluators.ragas_backed import RagasEvaluator


def test_raises_clear_error_when_ragas_not_available(monkeypatch):
    """Regardless of whether ragas is actually installed in this environment,
    the constructor must fail with a clear, actionable message when the
    extra isn't present — this is what a user hits if they reference
    track: ragas without `pip install evalkit[ragas]`."""
    monkeypatch.setattr(ragas_backed_module, "_RAGAS_AVAILABLE", False)
    with pytest.raises(ImportError, match=r"pip install evalkit\[ragas\]"):
        RagasEvaluator()


def test_registry_only_registers_ragas_when_available():
    """Guards against the bug this actually had during development: the
    wrapper module always imports successfully (it catches ImportError
    internally), so registration must check the availability flag, not
    just whether importing the module itself succeeded."""
    from evalkit.core.registry import Registry

    reg = Registry()
    if ragas_backed_module._RAGAS_AVAILABLE:
        reg.register_evaluator("ragas", RagasEvaluator)
        assert "ragas" in reg._evaluators
    else:
        assert "ragas" not in reg._evaluators


ragas = pytest.importorskip("ragas", reason="ragas extra not installed: pip install evalkit[ragas]")


class _FakeResult:
    def __init__(self, value):
        self.value = value


@pytest.fixture()
def mocked_ragas():
    with patch("evalkit.evaluators.ragas_backed.llm_factory"), patch(
        "evalkit.evaluators.ragas_backed.embedding_factory"
    ), patch("evalkit.evaluators.ragas_backed.Faithfulness") as mock_faithfulness, patch(
        "evalkit.evaluators.ragas_backed.ContextPrecision"
    ) as mock_context_precision, patch(
        "evalkit.evaluators.ragas_backed.ContextUtilization"
    ) as mock_context_utilization, patch(
        "evalkit.evaluators.ragas_backed.AnswerRelevancy"
    ) as mock_answer_relevancy, patch(
        "openai.AsyncOpenAI"
    ):
        mock_faithfulness.return_value.ascore = AsyncMock(return_value=_FakeResult(0.9))
        mock_context_utilization.return_value.ascore = AsyncMock(return_value=_FakeResult(0.7))
        mock_context_precision.return_value.ascore = AsyncMock(return_value=_FakeResult(0.8))
        mock_answer_relevancy.return_value.ascore = AsyncMock(return_value=_FakeResult(0.6))
        yield {
            "faithfulness": mock_faithfulness,
            "context_precision": mock_context_precision,
            "context_utilization": mock_context_utilization,
            "answer_relevancy": mock_answer_relevancy,
        }


def test_uses_context_utilization_when_no_reference(mocked_ragas):
    """No ground-truth reference in the dataset -> must use the
    reference-free ContextUtilization metric, not ContextPrecision (which
    requires one and would otherwise silently receive an empty string)."""
    evaluator = RagasEvaluator(metrics=["context_precision"])
    scores = evaluator.evaluate("q", "a", None, ["ctx"], None)

    assert scores == {"context_precision": 0.7}
    mocked_ragas["context_utilization"].return_value.ascore.assert_called_once_with(
        user_input="q", response="a", retrieved_contexts=["ctx"]
    )
    mocked_ragas["context_precision"].return_value.ascore.assert_not_called()


def test_uses_context_precision_when_reference_present(mocked_ragas):
    """A reference answer is available -> use the more accurate
    reference-based ContextPrecision metric instead."""
    evaluator = RagasEvaluator(metrics=["context_precision"])
    scores = evaluator.evaluate("q", "a", "the reference", ["ctx"], None)

    assert scores == {"context_precision": 0.8}
    mocked_ragas["context_precision"].return_value.ascore.assert_called_once_with(
        user_input="q", reference="the reference", retrieved_contexts=["ctx"]
    )
    mocked_ragas["context_utilization"].return_value.ascore.assert_not_called()


def test_all_metrics_computed_by_default(mocked_ragas):
    evaluator = RagasEvaluator()
    scores = evaluator.evaluate("q", "a", None, ["ctx"], None)
    assert set(scores.keys()) == {"faithfulness", "context_precision", "answer_relevancy", "hallucination_rate"}


def test_only_requested_metrics_are_computed(mocked_ragas):
    evaluator = RagasEvaluator(metrics=["faithfulness"])
    scores = evaluator.evaluate("q", "a", None, ["ctx"], None)
    assert set(scores.keys()) == {"faithfulness"}
    mocked_ragas["answer_relevancy"].assert_not_called()
