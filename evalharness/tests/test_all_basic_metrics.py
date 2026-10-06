"""
Unit tests validating all 10 basic evaluation metrics in evalharness.

Metrics verified:
1. Context precision (RagEvaluator.context_precision & RetrievalEvaluator.precision_at_k)
2. Context recall (RetrievalEvaluator.recall_at_k & RagEvaluator.context_recall)
3. Mean reciprocal ranking (RetrievalEvaluator.mrr)
4. Normalized discounted cumulative gain (RetrievalEvaluator.ndcg_at_k)
5. Faithfulness (RagEvaluator.faithfulness)
6. Answer relevance (RagEvaluator.answer_relevancy)
7. Traditional NLP metrics (TextSimilarityEvaluator: BLEU, ROUGE-L, BERTScore)
8. Answer correctness (RagEvaluator.answer_correctness)
9. Hallucination rate (RagEvaluator.hallucination_rate = 1.0 - faithfulness)
10. Latency and cost (Runner: latency_ms and cost)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from evalharness.contracts.adapter import AdapterResponse, BaseAdapter
from evalharness.contracts.judge_backend import BaseJudgeBackend
from evalharness.core.config import EvalConfig
from evalharness.core.runner import Runner
from evalharness.evaluators.rag import RagEvaluator
from evalharness.evaluators.retrieval import RetrievalEvaluator
from evalharness.evaluators.text_similarity import TextSimilarityEvaluator


class MockJudge(BaseJudgeBackend):
    def __init__(self, score_map: dict[str, float] | None = None) -> None:
        self.score_map = score_map or {}

    def score(self, prompt: str) -> float:
        for key, val in self.score_map.items():
            if key in prompt:
                return val
        return 0.85


def test_ndcg_at_k_calculation():
    evaluator = RetrievalEvaluator(metrics=["ndcg_at_k", "precision_at_k", "recall_at_k", "mrr"], k=3)
    context = ["chunk_a", "chunk_b", "chunk_c", "chunk_d"]
    metadata = {
        "relevant_chunks": ["chunk_a", "chunk_c"],
        "relevance_scores": {"chunk_a": 2.0, "chunk_c": 1.0},
    }
    scores = evaluator.evaluate(
        example_input="test query",
        output="test answer",
        reference="ref",
        context=context,
        metadata=metadata,
    )
    assert "ndcg_at_k" in scores
    assert 0.0 < scores["ndcg_at_k"] <= 1.0
    assert "precision_at_k" in scores
    assert "recall_at_k" in scores
    assert "mrr" in scores
    assert scores["mrr"] == 1.0


def test_rag_evaluator_all_metrics_including_context_recall_and_correctness():
    judge = MockJudge({
        "faithful": 0.90,
        "precision": 0.80,
        "context recall": 0.85,
        "relevancy": 0.95,
        "correctness": 0.92,
    })
    evaluator = RagEvaluator(
        judge=judge,
        metrics=[
            "faithfulness",
            "context_precision",
            "context_recall",
            "answer_relevancy",
            "answer_correctness",
            "hallucination_rate",
        ],
    )
    scores = evaluator.evaluate(
        example_input="What is the dimension of the embedding?",
        output="The embedding dimension is 1536.",
        reference="The embedding dimension is 1536 as specified in table 1.",
        context=["Table 1 reports embedding dimension = 1536."],
        metadata={},
    )
    assert scores["faithfulness"] == 0.90
    assert scores["hallucination_rate"] == pytest.approx(0.10, abs=1e-4)
    assert scores["context_precision"] == 0.80
    assert scores["context_recall"] == 0.85
    assert scores["answer_relevancy"] == 0.95
    assert scores["answer_correctness"] == 0.92


def test_traditional_nlp_metrics_bleu_rouge_bertscore():
    evaluator = TextSimilarityEvaluator(
        metrics=["exact_match", "f1", "bleu", "rouge_l", "bert_score"]
    )
    output = "Deep learning models require large scale datasets for training."
    reference = "Deep learning models require large datasets for effective training."

    mock_f1 = MagicMock()
    mock_f1.item.return_value = 0.88
    with patch("bert_score.score", return_value=(None, None, [mock_f1])):
        scores = evaluator.evaluate(
            example_input="q",
            output=output,
            reference=reference,
            context=[],
            metadata={},
        )
    assert "exact_match" in scores
    assert "f1" in scores
    assert "bleu" in scores
    assert "rouge_l" in scores
    assert "bert_score" in scores
    assert scores["f1"] > 0.70
    assert scores["bleu"] > 0.40
    assert scores["rouge_l"] > 0.70
    assert scores["bert_score"] == 0.88


class FullTrackMockAdapter(BaseAdapter):
    def run(self, example_input: str, metadata: dict | None = None) -> AdapterResponse:
        return AdapterResponse(
            output="Attention mechanisms allow dynamic weighting of input representations.",
            context=["Attention mechanisms compute attention weights across sequence representations."],
            latency_ms=150.0,
            metadata={
                "relevant_chunks": ["Attention mechanisms compute attention weights across sequence representations."],
                "prompt_tokens": 120,
                "completion_tokens": 30,
            },
        )


def test_runner_computes_and_aggregates_all_10_metrics(tmp_path, monkeypatch):
    from evalharness.core.registry import registry

    registry.register_adapter("test_metrics_eh:FullTrackMockAdapter", FullTrackMockAdapter)

    dataset_path = tmp_path / "dataset.jsonl"
    example = {
        "input": "How do attention mechanisms work?",
        "reference": "Attention mechanisms allow dynamic weighting of representations.",
        "context": ["Attention mechanisms compute attention weights across sequence representations."],
        "metadata": {
            "relevant_chunks": ["Attention mechanisms compute attention weights across sequence representations."],
        },
    }
    dataset_path.write_text(json.dumps(example) + "\n", encoding="utf-8")

    config = EvalConfig(
        track=["rag", "retrieval", "text_similarity"],
        dataset=str(dataset_path),
        adapter="test_metrics_eh:FullTrackMockAdapter",
        judge_backend="dummy",
        judge_model="dummy",
        metrics=[
            "faithfulness",
            "context_precision",
            "context_recall",
            "answer_relevancy",
            "answer_correctness",
            "hallucination_rate",
            "precision_at_k",
            "recall_at_k",
            "mrr",
            "ndcg_at_k",
            "bleu",
            "rouge_l",
            "bert_score",
        ],
    )

    runner = Runner(config)
    mock_f1 = MagicMock()
    mock_f1.item.return_value = 0.88
    with patch("bert_score.score", return_value=(None, None, [mock_f1])):
        result = runner.run()

    agg = result.aggregate()

    # 1. Context Precision
    assert "rag.context_precision" in agg or "retrieval.precision_at_k" in agg
    # 2. Context Recall
    assert "rag.context_recall" in agg or "retrieval.recall_at_k" in agg
    # 3. MRR
    assert "retrieval.mrr" in agg
    # 4. nDCG
    assert "retrieval.ndcg_at_k" in agg
    # 5. Faithfulness
    assert "rag.faithfulness" in agg
    # 6. Answer Relevance
    assert "rag.answer_relevancy" in agg
    # 7. Traditional NLP (BLEU, ROUGE, BERTScore)
    assert "text_similarity.bleu" in agg
    assert "text_similarity.rouge_l" in agg
    assert "text_similarity.bert_score" in agg
    # 8. Answer Correctness
    assert "rag.answer_correctness" in agg
    # 9. Hallucination Rate
    assert "rag.hallucination_rate" in agg
    # 10. Latency & Cost
    assert "latency_ms" in agg
    assert agg["latency_ms"] == 150.0
    assert "cost" in agg
    assert agg["cost"] > 0.0
