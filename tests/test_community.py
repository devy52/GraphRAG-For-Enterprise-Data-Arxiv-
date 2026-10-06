"""
Unit and Integration Tests for Graph Community Detection and Corpus-Level Summaries.

Architecture Role:
    Verifies Phase 14 / Post-Launch Stretch Goal 2:
    - Pure-Python Label Propagation Algorithm (LPA) clustering.
    - Community record synthesis, theme extraction, and degree-centrality ranking.
    - Corpus-level summary context generation for thematic queries.
    - In-memory caching and TTL expiration.
    - RetrievalCoordinator integration for macro-thematic overview queries.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from src.graph.community import (
    CACHE_TTL_SECONDS,
    CommunityDetectionResponse,
    CommunitySummaryRecord,
    GraphCommunityDetector,
)
from src.router.classifier import RouteClassifier
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RouteDecision


# ==============================================================================
# Unit Tests: Label Propagation Algorithm (LPA)
# ==============================================================================
def test_label_propagation_disjoint_clusters() -> None:
    """
    Verifies that LPA accurately segments two densely connected clusters with a weak bridge.
    Cluster 1: A, B, C (all pairwise connected)
    Cluster 2: X, Y, Z (all pairwise connected)
    Bridge: C - X
    """
    nodes = ["A", "B", "C", "X", "Y", "Z"]
    edges = [
        # Cluster 1 internal
        ("A", "EXTENDS", "B"),
        ("B", "EXTENDS", "C"),
        ("C", "EXTENDS", "A"),
        # Cluster 2 internal
        ("X", "EVALUATES_ON", "Y"),
        ("Y", "EVALUATES_ON", "Z"),
        ("Z", "EVALUATES_ON", "X"),
        # Bridge
        ("C", "RELATED_TO", "X"),
    ]

    labels = GraphCommunityDetector._run_label_propagation(nodes, edges)

    # All nodes in cluster 1 must share the same label
    assert labels["A"] == labels["B"] == labels["C"]
    # All nodes in cluster 2 must share the same label
    assert labels["X"] == labels["Y"] == labels["Z"]
    # Cluster 1 label must differ from cluster 2 label
    assert labels["A"] != labels["X"]


def test_label_propagation_empty_and_singletons() -> None:
    """Verifies LPA handles empty node sets and disconnected singletons."""
    assert GraphCommunityDetector._run_label_propagation([], []) == {}

    singletons = ["Node1", "Node2", "Node3"]
    labels = GraphCommunityDetector._run_label_propagation(singletons, [])
    # Each isolated node retains its initial distinct label
    assert len(set(labels.values())) == 3


# ==============================================================================
# Unit Tests: Community Record Synthesis
# ==============================================================================
def test_synthesize_community_record() -> None:
    """
    Verifies community summary synthesis derives appropriate titles, degree centrality,
    and thematic summaries from node types and edges.
    """
    detector = GraphCommunityDetector(writer=MagicMock())
    member_nodes = ["DPR", "ColBERT", "MS MARCO", "Karpukhin"]
    node_types = {
        "DPR": "Method",
        "ColBERT": "Method",
        "MS MARCO": "Dataset",
        "Karpukhin": "Author",
    }
    edges = [
        ("DPR", "EXTENDS", "ColBERT"),
        ("DPR", "EVALUATES_ON", "MS MARCO"),
        ("Karpukhin", "AUTHORED", "DPR"),
    ]

    record = detector._synthesize_community_record(
        community_id="community_01",
        member_nodes=member_nodes,
        node_types=node_types,
        edges=edges,
    )

    assert isinstance(record, CommunitySummaryRecord)
    assert record.community_id == "community_01"
    assert record.member_count == 4
    # DPR has highest degree (3 connections) -> should be first in top_entities
    assert record.top_entities[0] == "DPR"
    # Title combines method and dataset
    assert "DPR" in record.title and "MS MARCO" in record.title
    # Themes include method and dataset
    assert "DPR" in record.themes
    assert "MS MARCO" in record.themes
    assert "Investigates algorithmic methods" in record.summary
    assert "MS MARCO" in record.summary


# ==============================================================================
# Unit & Integration Tests: Detection, Caching & Context Formatting
# ==============================================================================
@pytest.mark.asyncio
async def test_detect_communities_and_caching() -> None:
    """
    Verifies detect_communities parses graph topology, caches results,
    and honors force_refresh.
    """
    detector = GraphCommunityDetector(writer=MagicMock())

    # Mock _fetch_graph_topology
    synthetic_node_types = {
        "BERT": "Method",
        "RoBERTa": "Method",
        "GLUE": "Dataset",
        "SQuAD": "Dataset",
    }
    synthetic_edges = [
        ("BERT", "EVALUATES_ON", "GLUE"),
        ("BERT", "EVALUATES_ON", "SQuAD"),
        ("RoBERTa", "EXTENDS", "BERT"),
        ("RoBERTa", "EVALUATES_ON", "GLUE"),
    ]
    detector._fetch_graph_topology = AsyncMock(return_value=(synthetic_node_types, synthetic_edges))

    # First call: computes and caches
    records1 = await detector.detect_communities()
    assert len(records1) >= 1
    assert detector._fetch_graph_topology.call_count == 1
    assert records1[0].member_count == 4

    # Second call without force_refresh: serves from cache
    records2 = await detector.detect_communities(force_refresh=False)
    assert records2 is records1
    assert detector._fetch_graph_topology.call_count == 1

    # Third call with force_refresh: triggers re-computation
    records3 = await detector.detect_communities(force_refresh=True)
    assert detector._fetch_graph_topology.call_count == 2
    assert len(records3) >= 1


@pytest.mark.asyncio
async def test_get_corpus_summary_context() -> None:
    """
    Verifies that get_corpus_summary_context generates a formatted markdown block
    and ranks communities by relevance to query keywords.
    """
    detector = GraphCommunityDetector(writer=MagicMock())
    c1 = CommunitySummaryRecord(
        community_id="community_01",
        title="Dense Passage Retrieval & Natural Questions Evaluation Cluster",
        member_count=12,
        top_entities=["DPR", "Natural Questions", "BM25"],
        summary="Dense passage retrieval methods evaluated on benchmark QA datasets.",
        themes=["DPR", "Natural Questions"],
    )
    c2 = CommunitySummaryRecord(
        community_id="community_02",
        title="GraphRAG & Knowledge Graphs Research",
        member_count=8,
        top_entities=["GraphRAG", "Neo4j", "HotpotQA"],
        summary="Graph-augmented retrieval over connected entities.",
        themes=["GraphRAG", "HotpotQA"],
    )
    detector.detect_communities = AsyncMock(return_value=[c1, c2])

    # 1. Unfiltered summary context
    summary_text = await detector.get_corpus_summary_context()
    assert "=== CORPUS-LEVEL RESEARCH COMMUNITIES (GRAPH SUMMARY) ===" in summary_text
    assert "[community_01]" in summary_text
    assert "[community_02]" in summary_text

    # 2. Query ranking by keyword
    ranked_text = await detector.get_corpus_summary_context(query="Tell me about Knowledge Graphs and GraphRAG", max_communities=1)
    assert "[community_02]" in ranked_text
    assert "[community_01]" not in ranked_text


# ==============================================================================
# Integration: RetrievalCoordinator Thematic Query Context Injection
# ==============================================================================
@pytest.mark.asyncio
async def test_coordinator_thematic_query_community_injection() -> None:
    """
    Verifies that RetrievalCoordinator detects high-level thematic queries (e.g. 'overview', 'summary')
    and automatically injects corpus-level community summaries into graph_facts.
    """
    mock_engine = MagicMock()
    mock_engine.identify_entities_in_text.return_value = []
    mock_engine.detect_best_template.return_value = None
    mock_engine.writer = MagicMock()

    mock_graph_result = MagicMock(
        raw_records=[],
        formatted_statements=[],
        source_chunk_ids=[],
        latency_ms=5.0,
    )
    mock_engine.query = AsyncMock(return_value=mock_graph_result)
    mock_engine.get_query_subgraph = AsyncMock(return_value={"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0})

    mock_vector = MagicMock()
    mock_vector.similarity_search = AsyncMock(return_value=[])

    mock_detector = MagicMock(spec=GraphCommunityDetector)
    mock_detector.get_corpus_summary_context = AsyncMock(
        return_value="=== CORPUS-LEVEL RESEARCH COMMUNITIES (GRAPH SUMMARY) ===\n[community_01] DPR Cluster"
    )

    coordinator = RetrievalCoordinator(
        classifier=RouteClassifier(query_engine=mock_engine, use_llm=False),
        query_engine=mock_engine,
        vector_store=mock_vector,
        community_detector=mock_detector,
    )

    thematic_query = "Give me a high-level summary overview of research themes across the corpus"
    ctx = await coordinator.retrieve(thematic_query)

    assert mock_detector.get_corpus_summary_context.called
    assert len(ctx.graph_facts) > 0
    assert "CORPUS-LEVEL RESEARCH COMMUNITIES" in ctx.graph_facts[0]
