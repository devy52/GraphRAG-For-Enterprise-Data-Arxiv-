"""
Unit tests validating GraphRAG-specific evaluation dimensions in evalkit.

Metrics verified:
1. Layer 1 (Indexing):
   - entity_relation_coverage: Triplet and entity recall against gold reference
   - community_coherence: Faithfulness of community summaries to member data
2. Layer 2 (Search):
   - graph_utilization_rate: Traversal efficiency (used vs retrieved graph facts)
3. Layer 3 (Generation):
   - global_diversity: Thematic breadth and non-repetition on global queries
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from evalkit.contracts.adapter import AdapterResponse, BaseAdapter
from evalkit.contracts.judge_backend import BaseJudgeBackend
from evalkit.core.config import EvalConfig
from evalkit.core.runner import Runner
from evalkit.evaluators.graph import (
    GraphEvaluator,
    compute_entity_relation_coverage_sets,
    compute_graph_utilization_rate,
    compute_lexical_diversity,
    compute_thematic_coverage,
)


class MockJudge(BaseJudgeBackend):
    def __init__(self, score_val: float = 0.95) -> None:
        self.score_val = score_val

    def score(self, prompt: str) -> float:
        return self.score_val


class MockGraphAdapter(BaseAdapter):
    def run(self, example_input: str, metadata: dict | None = None) -> AdapterResponse:
        return AdapterResponse(
            output="Hierarchical Navigable Small World (HNSW) graphs and Vector Quantization enable sub-millisecond retrieval.",
            context=[
                "[graph] (:Paper {id: '2301.001'})-[:USES_METHOD]->(:Method {name: 'HNSW'})",
                "[graph] (:Paper {id: '2301.001'})-[:EVALUATED_ON]->(:Dataset {name: 'Sift1M'})",
                "[retrieved] Vector search indexes enable scalable semantic matching.",
            ],
            latency_ms=12.5,
            metadata={
                "graph_facts_retrieved": [
                    "(:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})",
                    "(:Paper)-[:EVALUATED_ON]->(:Dataset {name: 'Sift1M'})",
                ],
                "graph_facts_used": [
                    "(:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})",
                ],
                "expected_themes": ["HNSW", "Vector Quantization", "Graph Indexing"],
                "community_summary": "Vector and graph indexing techniques improve search throughput.",
                "community_chunks": ["Chunk 1: HNSW graphs.", "Chunk 2: Vector quantization."],
                "gold_entities": ["HNSW", "Sift1M"],
                "extracted_entities": ["HNSW"],
                "gold_relations": [("Paper", "USES_METHOD", "HNSW")],
                "extracted_relations": [("Paper", "USES_METHOD", "HNSW")],
            },
        )


def test_graph_utilization_rate_calculation():
    # 1. Explicit used vs retrieved
    rate = compute_graph_utilization_rate(
        output="Arbitrary answer text",
        graph_facts_retrieved=["fact1", "fact2", "fact3", "fact4"],
        graph_facts_used=["fact1", "fact2"],
    )
    assert rate == 0.50

    # 2. Statement matching heuristic when explicit used is not given
    retrieved = [
        "(:Paper {id: 'P1'})-[:USES_METHOD]->(:Method {name: 'HNSW'})",
        "(:Paper {id: 'P1'})-[:USES_METHOD]->(:Method {name: 'BM25'})",
    ]
    rate_matched = compute_graph_utilization_rate(
        output="The authors evaluate HNSW for graph-based retrieval.",
        graph_facts_retrieved=retrieved,
    )
    # HNSW matches, BM25 does not -> 1 / 2 = 0.5
    assert rate_matched == 0.50

    # 3. Empty retrieved facts -> 0.0
    assert compute_graph_utilization_rate(output="Test", graph_facts_retrieved=[]) == 0.0


def test_global_diversity_and_thematic_coverage():
    # Repetitive text has low diversity
    repetitive = "rag rag rag rag rag rag is is is good good good"
    diverse = "Knowledge graphs capture topological relations between scholarly citations, datasets, and benchmark baselines."

    div_rep = compute_lexical_diversity(repetitive)
    div_good = compute_lexical_diversity(diverse)
    assert div_good > div_rep

    # Thematic coverage
    themes = ["citation", "benchmark", "quantization"]
    cov = compute_thematic_coverage(diverse, themes)
    # "citation" and "benchmark" appear in `diverse`, "quantization" does not -> 2/3 = 0.6667
    assert cov == pytest.approx(0.6667, abs=0.01)


def test_entity_relation_coverage_sets():
    gold_ent = ["Neo4j", "pgvector", "FastAPI"]
    ext_ent = ["Neo4j", "FastAPI"]  # 2/3 = 0.6667

    gold_rel = [("System", "USES", "Neo4j"), ("System", "USES", "pgvector")]
    ext_rel = [("System", "USES", "Neo4j")]  # 1/2 = 0.50

    coverage = compute_entity_relation_coverage_sets(
        extracted_entities=ext_ent,
        gold_entities=gold_ent,
        extracted_relations=ext_rel,
        gold_relations=gold_rel,
    )
    # (2/3 + 1/2) / 2 = 0.5833
    assert coverage == pytest.approx(0.5833, abs=0.01)


def test_graph_evaluator_direct_evaluation():
    judge = MockJudge(score_val=0.92)
    evaluator = GraphEvaluator(judge=judge)

    scores = evaluator.evaluate(
        example_input="What indexing techniques are used?",
        output="The system relies on HNSW graphs for fast approximate nearest neighbor search.",
        reference="The system combines HNSW graphs and Vector Quantization.",
        context=[
            "[graph] (:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})",
            "[graph] (:Paper)-[:EVALUATED_ON]->(:Dataset {name: 'Sift1M'})",
        ],
        metadata={
            "graph_facts_retrieved": [
                "(:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})",
                "(:Paper)-[:EVALUATED_ON]->(:Dataset {name: 'Sift1M'})",
            ],
            "graph_facts_used": [
                "(:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})",
            ],
            "expected_themes": ["HNSW", "ANN Search"],
            "community_summary": "Graph indexing via HNSW.",
            "community_chunks": ["Chunk on HNSW."],
            "gold_entities": ["HNSW"],
            "extracted_entities": ["HNSW"],
        },
    )

    assert "graph_utilization_rate" in scores
    assert scores["graph_utilization_rate"] == 0.50
    assert "global_diversity" in scores
    assert scores["global_diversity"] > 0.50
    assert "community_coherence" in scores
    assert scores["community_coherence"] == 0.92
    assert "entity_relation_coverage" in scores
    assert scores["entity_relation_coverage"] == 1.0


def test_runner_with_graph_track(tmp_path):
    from evalkit.core.registry import registry

    registry.register_adapter("test_graph:MockGraphAdapter", MockGraphAdapter)

    dataset_path = tmp_path / "graph_dataset.jsonl"
    example = {
        "input": "What vector indexing methods are used?",
        "reference": "HNSW and Vector Quantization.",
        "context": ["[graph] (:Paper)-[:USES_METHOD]->(:Method {name: 'HNSW'})"],
        "metadata": {
            "expected_themes": ["HNSW", "Vector Quantization"],
            "gold_entities": ["HNSW", "Sift1M"],
            "extracted_entities": ["HNSW"],
        },
    }
    dataset_path.write_text(json.dumps(example) + "\n", encoding="utf-8")

    config = EvalConfig(
        track="graph",
        dataset=str(dataset_path),
        adapter="test_graph:MockGraphAdapter",
        judge_backend="dummy",
        judge_model="dummy",
        metrics=[
            "graph_utilization_rate",
            "community_coherence",
            "global_diversity",
            "entity_relation_coverage",
        ],
    )

    runner = Runner(config)
    result = runner.run()
    agg = result.aggregate()

    assert "graph_utilization_rate" in agg
    assert "community_coherence" in agg
    assert "global_diversity" in agg
    assert "entity_relation_coverage" in agg
    assert "latency_ms" in agg
    assert "cost" in agg
