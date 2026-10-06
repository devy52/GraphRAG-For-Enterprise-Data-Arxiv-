"""
Unit tests for CanonicalEntityResolver (ADR 053 / Run 3B).
"""

import pytest
from src.graph.canonical_resolver import (
    CanonicalEntityResolver,
    ResolutionResult,
    CONFIDENCE_THRESHOLD,
    AMBIGUITY_DELTA_THRESHOLD,
)
from src.graph.models import EntityType


@pytest.fixture
def resolver():
    res = CanonicalEntityResolver()
    # Register dummy graph entities for testing
    res.register_graph_entities([
        ("Reinforcement Learning", EntityType.METHOD, ["RL", "reinforcement learning policy"]),
        ("Agentic RAG", EntityType.METHOD, ["Agentic Retrieval-Augmented Generation"]),
        ("IslamicFaithQA", EntityType.DATASET, ["Islamic Faith QA"]),
        ("HotpotQA", EntityType.DATASET, ["Hotpot QA"]),
        ("Patrick Lewis", EntityType.AUTHOR, ["P. Lewis"]),
        # Two very similar methods to test ambiguity gate
        ("Hierarchical Subgraph Indexing", EntityType.METHOD, []),
        ("Hierarchical Subgraph Search", EntityType.METHOD, []),
    ])
    return res


def test_tier1_canonical_id_exact_match(resolver):
    """Tier 1: Canonical document ID resolves with 1.0 confidence and canonical_id."""
    res = resolver.resolve("arxiv_2603.01661v2")
    assert res.accepted is True
    assert res.match_method == "canonical_id"
    assert res.canonical_id == "arxiv_2603.01661v2"
    assert res.top_score == 1.0
    assert len(res.candidate_set) >= 1
    assert res.candidate_set[0].canonical_id == "arxiv_2603.01661v2"


def test_tier2_normalized_arxiv_id_match(resolver):
    """Tier 2: Bare or query-embedded arXiv ID resolves correctly."""
    res = resolver.resolve("2507.23581v2", query_text="What is in paper 2507.23581v2?")
    assert res.accepted is True
    assert res.match_method == "normalized_arxiv_id"
    assert res.canonical_id == "arxiv_2507.23581v2"
    assert res.top_score == 1.0


def test_tier3_exact_normalized_title_match(resolver):
    """Tier 3: Exact title match (normalized) resolves to catalog paper."""
    res = resolver.resolve("when to use graphs in rag: a comprehensive analysis for graph retrieval-augmented generation")
    assert res.accepted is True
    assert res.match_method == "exact_normalized_title"
    assert res.canonical_id == "arxiv_2506.05690v3"
    assert res.top_score == 1.0


def test_tier4_curated_alias_match(resolver):
    """Tier 4: Curated aliases map directly to canonical paper ID and name."""
    cases = [
        ("HeRo", "arxiv_2603.01661v2", "HeRo", EntityType.PAPER),
        ("GraphRAG-R1", "arxiv_2507.23581v2", "GraphRAG-R1", EntityType.PAPER),
        ("GraphSearch", "arxiv_2509.22009v2", "GraphSearch", EntityType.PAPER),
        ("ACE-GraphRAG", "arxiv_2608.01269v2", "ACE-GraphRAG", EntityType.PAPER),
        ("Dissecting Agentic RAG", "arxiv_2606.21553v1", "Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model", EntityType.PAPER),
    ]
    for surface, expected_id, expected_name, expected_type in cases:
        res = resolver.resolve(surface)
        assert res.accepted is True, f"Failed for {surface}"
        assert res.match_method == "alias_table"
        assert res.canonical_id == expected_id
        assert res.canonical_name == expected_name
        assert res.entity_type == expected_type


def test_tier5_controlled_token_similarity_success(resolver):
    """Tier 5: High token overlap (>= 0.85) without ambiguity succeeds."""
    # "Reinforcement Learning Policy" vs registered "Reinforcement Learning"
    res = resolver.resolve("Reinforcement Learning Approach", expected_type=EntityType.METHOD)
    # Tokens: {'reinforcement', 'learning', 'approach'} vs {'reinforcement', 'learning'} -> Jaccard = 2/3 = 0.6667 (below 0.85 -> low_confidence)
    assert res.accepted is False
    assert res.reason == "low_confidence"


def test_tier6_ambiguity_rejection_close_tie(resolver):
    """Tier 6 Safeguard: Two competing candidates within delta < 0.15 must be rejected."""
    # "Hierarchical Subgraph" has equal token overlap with both "Hierarchical Subgraph Indexing" and "Hierarchical Subgraph Search"
    res = resolver.resolve("Hierarchical Subgraph", expected_type=EntityType.METHOD)
    assert res.accepted is False
    assert res.reason in ("ambiguous", "low_confidence")
    assert res.ambiguity_count >= 2
    # Verify candidate set is preserved
    assert len(res.candidate_set) >= 2


def test_negative_test_tempting_wrong_candidate_rejection(resolver):
    """Negative test: Confusing query entity that does not meet threshold must be rejected."""
    # Fake / tempting query
    res = resolver.resolve("NonExistent Quantum Graph Model 2026")
    assert res.accepted is False
    assert res.top_score < CONFIDENCE_THRESHOLD
    assert res.reason in ("low_confidence", "no_candidates")


def test_audit_ledger_preserves_candidates(resolver):
    """Safeguard 2: Resolution audit records candidate set, top_score, and second_score."""
    resolver.resolve("HeRo")
    resolver.resolve("Hierarchical Subgraph")
    log = resolver.resolution_audit_log
    assert len(log) >= 2

    # Verify accepted audit record
    hero_rec = [r for r in log if r["requested_entity"] == "HeRo"][0]
    assert hero_rec["accepted"] is True
    assert hero_rec["canonical_id"] == "arxiv_2603.01661v2"
    assert hero_rec["match_method"] == "alias_table"
    assert len(hero_rec["candidate_set"]) >= 1

    # Verify rejected audit record
    ambig_rec = [r for r in log if r["requested_entity"] == "Hierarchical Subgraph"][0]
    assert ambig_rec["accepted"] is False
    assert ambig_rec["reason"] in ("ambiguous", "low_confidence")
