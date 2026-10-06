from __future__ import annotations

import pytest

from evalkit.adapters.static import StaticAdapter
from evalkit.evaluators.generic import GenericEvaluator
from evalkit.evaluators.rag import RagEvaluator
from evalkit.judges.dummy_judge import DummyJudgeBackend


def test_static_adapter_returns_precomputed_output():
    adapter = StaticAdapter()
    result = adapter.run("input", metadata={"precomputed_output": "the answer"})
    assert result == "the answer"


def test_static_adapter_raises_without_precomputed_output():
    adapter = StaticAdapter()
    with pytest.raises(ValueError, match="precomputed_output"):
        adapter.run("input", metadata={})


def test_static_adapter_raises_with_no_metadata():
    adapter = StaticAdapter()
    with pytest.raises(ValueError, match="precomputed_output"):
        adapter.run("input", metadata=None)


def test_rag_evaluator_only_computes_requested_metrics():
    judge = DummyJudgeBackend()
    evaluator = RagEvaluator(judge=judge, metrics=["faithfulness"])
    scores = evaluator.evaluate(
        example_input="q", output="a", reference=None, context=["ctx"], metadata=None
    )
    assert set(scores.keys()) == {"faithfulness"}


def test_rag_evaluator_defaults_to_all_metrics():
    judge = DummyJudgeBackend()
    evaluator = RagEvaluator(judge=judge, metrics=None)
    scores = evaluator.evaluate(
        example_input="q", output="a", reference=None, context=["ctx"], metadata=None
    )
    assert set(scores.keys()) == {"faithfulness", "context_precision", "answer_relevancy", "hallucination_rate"}


def test_rag_evaluator_handles_missing_context():
    """A RAG system with a retrieval miss should still score, not crash —
    empty context is a real (and important-to-catch) case, not an error."""
    judge = DummyJudgeBackend()
    evaluator = RagEvaluator(judge=judge, metrics=["faithfulness"])
    scores = evaluator.evaluate(
        example_input="q", output="a", reference=None, context=None, metadata=None
    )
    assert "faithfulness" in scores


def test_generic_evaluator_uses_reference_when_present():
    """Not a behavior assertion on the score itself (that depends on the
    judge), just that the reference actually reaches the prompt sent to the
    judge — otherwise a 'reference-aware' evaluator would silently ignore
    the reference."""
    captured_prompts = []

    class RecordingJudge(DummyJudgeBackend):
        def score(self, prompt: str) -> float:
            captured_prompts.append(prompt)
            return super().score(prompt)

    evaluator = GenericEvaluator(judge=RecordingJudge(), metrics=["quality"])
    evaluator.evaluate(
        example_input="q", output="a", reference="the reference answer", context=None, metadata=None
    )
    assert "the reference answer" in captured_prompts[0]


def test_generic_evaluator_returns_empty_when_metric_not_requested():
    evaluator = GenericEvaluator(judge=DummyJudgeBackend(), metrics=["something_else"])
    scores = evaluator.evaluate(
        example_input="q", output="a", reference=None, context=None, metadata=None
    )
    assert scores == {}
