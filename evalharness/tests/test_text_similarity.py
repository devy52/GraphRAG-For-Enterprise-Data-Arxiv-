from __future__ import annotations

from unittest.mock import patch

import pytest

from evalharness.evaluators.text_similarity import TextSimilarityEvaluator, _token_f1, _cosine_similarity


def test_no_reference_returns_empty():
    evaluator = TextSimilarityEvaluator()
    scores = evaluator.evaluate("q", "some output", None, None, None)
    assert scores == {}


def test_exact_match_true():
    evaluator = TextSimilarityEvaluator(metrics=["exact_match"])
    scores = evaluator.evaluate("q", "Paris", "Paris", None, None)
    assert scores == {"exact_match": 1.0}


def test_exact_match_false():
    evaluator = TextSimilarityEvaluator(metrics=["exact_match"])
    scores = evaluator.evaluate("q", "Paris, France", "Paris", None, None)
    assert scores == {"exact_match": 0.0}


def test_exact_match_ignores_surrounding_whitespace():
    evaluator = TextSimilarityEvaluator(metrics=["exact_match"])
    scores = evaluator.evaluate("q", "  Paris  ", "Paris", None, None)
    assert scores == {"exact_match": 1.0}


def test_f1_identical_is_one():
    assert _token_f1("the cat sat on the mat", "the cat sat on the mat") == 1.0


def test_f1_no_overlap_is_zero():
    assert _token_f1("completely different words here", "totally unrelated text entirely") == 0.0


def test_f1_partial_overlap_between_zero_and_one():
    score = _token_f1("the cat sat", "the cat stood")
    assert 0.0 < score < 1.0


def test_f1_empty_output_and_reference_both_empty_is_one():
    assert _token_f1("", "") == 1.0


def test_f1_empty_output_nonempty_reference_is_zero():
    assert _token_f1("", "something") == 0.0


def test_f1_metric_in_evaluator():
    evaluator = TextSimilarityEvaluator(metrics=["f1"])
    scores = evaluator.evaluate("q", "the cat sat on the mat", "the cat sat on the mat", None, None)
    assert scores["f1"] == 1.0


def test_cosine_similarity_identical_vectors():
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_does_not_crash():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_bleu_requires_extra_raises_clear_error_when_unavailable(monkeypatch):
    import evalharness.evaluators.text_similarity as mod

    monkeypatch.setattr(mod, "_SACREBLEU_AVAILABLE", False)
    evaluator = TextSimilarityEvaluator(metrics=["bleu"])
    with pytest.raises(ImportError, match=r"pip install evalharness\[text-metrics\]"):
        evaluator.evaluate("q", "output", "reference", None, None)


def test_rouge_requires_extra_raises_clear_error_when_unavailable(monkeypatch):
    import evalharness.evaluators.text_similarity as mod

    monkeypatch.setattr(mod, "_ROUGE_AVAILABLE", False)
    evaluator = TextSimilarityEvaluator(metrics=["rouge_l"])
    with pytest.raises(ImportError, match=r"pip install evalharness\[text-metrics\]"):
        evaluator.evaluate("q", "output", "reference", None, None)


def test_embedding_similarity_uses_litellm_and_computes_cosine():
    fake_response = {
        "data": [
            {"embedding": [1.0, 0.0]},
            {"embedding": [1.0, 0.0]},
        ]
    }
    with patch("litellm.embedding", return_value=fake_response) as mock_embed:
        evaluator = TextSimilarityEvaluator(metrics=["embedding_similarity"])
        scores = evaluator.evaluate("q", "output text", "reference text", None, None)

    assert scores["embedding_similarity"] == pytest.approx(1.0)
    _, kwargs = mock_embed.call_args
    assert kwargs["input"] == ["output text", "reference text"]


def test_only_requested_metrics_computed():
    evaluator = TextSimilarityEvaluator(metrics=["exact_match"])
    scores = evaluator.evaluate("q", "a", "a", None, None)
    assert set(scores.keys()) == {"exact_match"}


def test_all_metrics_default_when_dependencies_available():
    if not TextSimilarityEvaluator.ALL_METRICS:
        pytest.skip("no metrics defined")
    evaluator = TextSimilarityEvaluator()
    assert set(evaluator.metrics) == set(TextSimilarityEvaluator.ALL_METRICS)


# -- Real BLEU/ROUGE computation (skipped if the text-metrics extra isn't installed) --

sacrebleu = pytest.importorskip("sacrebleu", reason="text-metrics extra not installed")
pytest.importorskip("rouge_score", reason="text-metrics extra not installed")


def test_bleu_identical_text_scores_near_one():
    evaluator = TextSimilarityEvaluator(metrics=["bleu"])
    scores = evaluator.evaluate("q", "the cat sat on the mat", "the cat sat on the mat", None, None)
    assert scores["bleu"] > 0.95


def test_bleu_unrelated_text_scores_near_zero():
    evaluator = TextSimilarityEvaluator(metrics=["bleu"])
    scores = evaluator.evaluate("q", "quantum physics is fascinating", "the cat sat on the mat", None, None)
    assert scores["bleu"] < 0.1


def test_rouge_l_identical_text_scores_near_one():
    evaluator = TextSimilarityEvaluator(metrics=["rouge_l"])
    scores = evaluator.evaluate("q", "the cat sat on the mat", "the cat sat on the mat", None, None)
    assert scores["rouge_l"] > 0.95


def test_rouge_l_unrelated_text_scores_low():
    evaluator = TextSimilarityEvaluator(metrics=["rouge_l"])
    scores = evaluator.evaluate("q", "quantum physics is fascinating", "the cat sat on the mat", None, None)
    assert scores["rouge_l"] < 0.3
