from __future__ import annotations

from evalharness.evaluators.retrieval import RetrievalEvaluator, _lexical_overlap


def test_precision_recall_mrr_with_ground_truth():
    evaluator = RetrievalEvaluator(metrics=["precision_at_k", "recall_at_k", "mrr"])
    context = ["chunk A", "chunk B", "chunk C"]
    metadata = {"relevant_chunks": ["chunk B"]}

    scores = evaluator.evaluate("q", "output", None, context, metadata)

    assert scores["precision_at_k"] == 1 / 3  # 1 of 3 retrieved chunks relevant
    assert scores["recall_at_k"] == 1.0  # the only relevant chunk was retrieved
    assert scores["mrr"] == 1 / 2  # relevant chunk is at rank 2


def test_mrr_zero_when_relevant_chunk_not_retrieved():
    evaluator = RetrievalEvaluator(metrics=["mrr"])
    context = ["chunk A", "chunk B"]
    metadata = {"relevant_chunks": ["chunk Z"]}  # not in context at all

    scores = evaluator.evaluate("q", "output", None, context, metadata)
    assert scores["mrr"] == 0.0


def test_precision_at_k_respects_k_limit():
    evaluator = RetrievalEvaluator(metrics=["precision_at_k"], k=2)
    context = ["relevant", "irrelevant", "relevant"]  # 3rd relevant chunk is outside k=2
    metadata = {"relevant_chunks": ["relevant"]}

    scores = evaluator.evaluate("q", "output", None, context, metadata)
    # only first 2 considered: 1 relevant out of 2
    assert scores["precision_at_k"] == 0.5


def test_no_ground_truth_skips_ranking_metrics_without_crashing():
    """Most datasets won't have relevant_chunks on day one — must not error,
    must just report nothing for these three metrics."""
    evaluator = RetrievalEvaluator(metrics=["precision_at_k", "recall_at_k", "mrr"])
    scores = evaluator.evaluate("q", "output", None, ["chunk A"], None)
    assert scores == {}


def test_relevance_matching_is_exact_string_not_fuzzy():
    """Documented limitation: 'Chunk B' != 'chunk B'. This is intentional
    and must stay this way unless the contract docstring is updated too."""
    evaluator = RetrievalEvaluator(metrics=["recall_at_k"])
    context = ["chunk B"]
    metadata = {"relevant_chunks": ["Chunk B"]}  # different case
    scores = evaluator.evaluate("q", "output", None, context, metadata)
    assert scores["recall_at_k"] == 0.0


def test_lexical_overlap_identical_text_is_one():
    assert _lexical_overlap("the cat sat", "the cat sat") == 1.0


def test_lexical_overlap_no_shared_words_is_zero():
    assert _lexical_overlap("completely unrelated", "totally different topic") == 0.0


def test_lexical_overlap_empty_string_is_zero():
    assert _lexical_overlap("", "something") == 0.0


def test_chunk_utilization_high_when_output_reflects_chunks():
    evaluator = RetrievalEvaluator(metrics=["chunk_utilization"])
    context = ["The Eiffel Tower was completed in 1889", "Unrelated chunk about penguins"]
    output = "The Eiffel Tower was completed in 1889."

    scores = evaluator.evaluate("q", output, None, context, None)
    # only the first chunk shares vocabulary with the output
    assert scores["chunk_utilization"] == 0.5


def test_chunk_utilization_zero_with_no_context():
    evaluator = RetrievalEvaluator(metrics=["chunk_utilization"])
    scores = evaluator.evaluate("q", "output", None, None, None)
    assert "chunk_utilization" not in scores  # no context -> nothing to measure


def test_only_requested_metrics_computed():
    evaluator = RetrievalEvaluator(metrics=["chunk_utilization"])
    scores = evaluator.evaluate("q", "output text", None, ["output text"], {"relevant_chunks": ["x"]})
    assert set(scores.keys()) == {"chunk_utilization"}
