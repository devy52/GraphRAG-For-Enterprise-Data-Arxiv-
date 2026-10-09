"""
Tests for Bounded LangGraph Evidence Refinement (ADR 070).

Verifies:
1. Heuristic evidence gap detection (corpus entities and catalog document IDs).
2. Fast-path routing when evidence is sufficient or queries are out-of-scope.
3. LangGraph node execution and strict resource budget capping (<= 3 facts, <= 2 chunks).
4. Provenance tracking: registration of refined chunk IDs into cited_chunk_ids.
5. RetrievalCoordinator integration: conditional invocation, fast path, and graceful fallback on exceptions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.graph.query_engine import GraphQueryResult
from src.graph.templates import QueryTemplateType
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RetrievalContext, RouteDecision, RoutingResult
from src.router.refiner import EvidenceRefiner, RefinementState
from src.vector.models import VectorSearchResult


@pytest.fixture
def mock_query_engine():
    engine = MagicMock()
    # By default, mock identify_entities_in_text
    engine.identify_entities_in_text = MagicMock(return_value=[])
    engine.execute_query = AsyncMock(return_value=GraphQueryResult(
        formatted_statements=["Entity DPR [:extends] BM25 [chunk: 2004_04906_001]"],
        source_chunk_ids=["2004_04906_001"],
        template_type=QueryTemplateType.EGO_NEIGHBORHOOD,
    ))
    return engine


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.similarity_search = AsyncMock(return_value=[
        VectorSearchResult(
            chunk_id="2004_04906_002",
            document_id="2004_04906",
            paper_title="Dense Passage Retrieval",
            section_path="Abstract",
            text="DPR trains dense retrievers using dual encoders.",
            score=0.88,
        )
    ])
    return store


@pytest.fixture
def mock_metadata_resolver():
    resolver = MagicMock()
    resolver._indexed_papers = [
        {
            "paper_id": "2004.04906",
            "title": "Dense Passage Retrieval for Open-Domain Question Answering",
        },
        {
            "paper_id": "1706.03762",
            "title": "Attention Is All You Need",
        },
    ]
    return resolver


@pytest.fixture
def refiner(mock_query_engine, mock_vector_store, mock_metadata_resolver):
    return EvidenceRefiner(
        query_engine=mock_query_engine,
        vector_store=mock_vector_store,
        metadata_resolver=mock_metadata_resolver,
        max_refined_facts=3,
        max_refined_chunks=2,
    )


# ------------------------------------------------------------------------------
# 1. Evidence Gap Detector Tests
# ------------------------------------------------------------------------------

def test_evidence_gap_detector_triggers_on_missing_entity(refiner, mock_query_engine):
    """Detects gap when query contains an ontology entity missing from retrieved context."""
    mock_query_engine.identify_entities_in_text.return_value = [("Dense Passage Retrieval", "Method")]

    initial_facts = ["Some unrelated graph fact."]
    initial_chunks = [
        VectorSearchResult(
            chunk_id="chunk_001",
            document_id="doc_1",
            paper_title="BERT Paper",
            section_path="Introduction",
            text="Unrelated text about BERT.",
            score=0.75,
        )
    ]

    has_gap, missing_ents, missing_docs = refiner.detect_evidence_gap(
        query="What is Dense Passage Retrieval?",
        graph_facts=initial_facts,
        retrieved_chunks=initial_chunks,
    )

    assert has_gap is True
    assert "Dense Passage Retrieval" in missing_ents


def test_evidence_gap_detector_fast_paths_when_entity_present(refiner, mock_query_engine):
    """Bypasses refinement when entity is already covered in graph facts or chunk text."""
    mock_query_engine.identify_entities_in_text.return_value = [("Dense Passage Retrieval", "Method")]

    initial_facts = ["Dense Passage Retrieval uses dual encoders [chunk: 2004_04906_001]"]
    initial_chunks = []

    has_gap, missing_ents, missing_docs = refiner.detect_evidence_gap(
        query="What is Dense Passage Retrieval?",
        graph_facts=initial_facts,
        retrieved_chunks=initial_chunks,
    )

    assert has_gap is False
    assert missing_ents == []
    assert missing_docs == []


def test_evidence_gap_detector_triggers_on_missing_paper_id(refiner):
    """Detects gap when a specifically queried paper is absent from retrieved doc IDs."""
    initial_facts = []
    initial_chunks = [
        VectorSearchResult(
            chunk_id="chunk_1706_03762_001",
            document_id="1706_03762",
            paper_title="Attention Is All You Need",
            section_path="Abstract",
            text="Transformers use multi-head self-attention.",
            score=0.91,
        )
    ]

    has_gap, missing_ents, missing_docs = refiner.detect_evidence_gap(
        query="Explain paper 2004.04906 in detail.",
        graph_facts=initial_facts,
        retrieved_chunks=initial_chunks,
    )

    assert has_gap is True
    assert any("2004" in d for d in missing_docs)


def test_evidence_gap_detector_out_of_scope_fast_path(refiner, mock_query_engine):
    """Out-of-scope query has no corpus entities or papers -> zero gap -> fast path."""
    mock_query_engine.identify_entities_in_text.return_value = []

    has_gap, missing_ents, missing_docs = refiner.detect_evidence_gap(
        query="What is the capital of Australia?",
        graph_facts=[],
        retrieved_chunks=[],
    )

    assert has_gap is False
    assert missing_ents == []
    assert missing_docs == []


# ------------------------------------------------------------------------------
# 2. Refinement Nodes & Resource Budget Bounds Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refinement_budget_caps_strictly_enforced(refiner):
    """Ensures merge_evidence_node strictly caps at max_refined_facts and max_refined_chunks."""
    refiner.max_refined_facts = 2
    refiner.max_refined_chunks = 1

    state: RefinementState = {
        "query": "Test query",
        "initial_graph_facts": ["Initial fact 1"],
        "initial_chunk_ids": ["init_chunk_1"],
        "refined_graph_facts": [
            "Candidate fact 1",
            "Candidate fact 2",
            "Candidate fact 3",
            "Candidate fact 4",
        ],
        "refined_chunks": [
            VectorSearchResult(chunk_id="c1", document_id="d1", paper_title="P1", section_path="S1", text="t1", score=0.9),
            VectorSearchResult(chunk_id="c2", document_id="d2", paper_title="P2", section_path="S2", text="t2", score=0.8),
            VectorSearchResult(chunk_id="c3", document_id="d3", paper_title="P3", section_path="S3", text="t3", score=0.7),
        ],
    }

    result = await refiner.merge_evidence_node(state)

    assert len(result["refined_graph_facts"]) == 2
    assert len(result["refined_chunks"]) == 1
    assert result["refined_chunks"][0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_refinement_deduplicates_against_initial_evidence(refiner):
    """Ensures existing facts and chunk IDs from initial retrieval are not duplicated."""
    state: RefinementState = {
        "query": "Test query",
        "initial_graph_facts": ["Existing Fact A"],
        "initial_chunk_ids": ["chunk_existing_1"],
        "refined_graph_facts": [
            "Existing Fact A",  # Duplicate
            "Brand New Fact B",
        ],
        "refined_chunks": [
            VectorSearchResult(chunk_id="chunk_existing_1", document_id="d1", paper_title="P1", section_path="S1", text="existing", score=0.9),
            VectorSearchResult(chunk_id="chunk_new_2", document_id="d2", paper_title="P2", section_path="S2", text="new", score=0.85),
        ],
    }

    result = await refiner.merge_evidence_node(state)

    assert result["refined_graph_facts"] == ["Brand New Fact B"]
    assert len(result["refined_chunks"]) == 1
    assert result["refined_chunks"][0].chunk_id == "chunk_new_2"


# ------------------------------------------------------------------------------
# 3. RetrievalCoordinator Integration Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coordinator_fast_path_when_refinement_disabled(
    mock_query_engine, mock_vector_store, mock_metadata_resolver
):
    """Coordinator with enable_evidence_refinement=False skips refinement entirely."""
    coordinator = RetrievalCoordinator(
        query_engine=mock_query_engine,
        vector_store=mock_vector_store,
        metadata_resolver=mock_metadata_resolver,
        enable_evidence_refinement=False,
    )
    coordinator.classifier = MagicMock()
    coordinator.classifier.classify = AsyncMock(return_value=RoutingResult(
        decision=RouteDecision.BOTH,
        confidence=0.95,
        reasoning="Test",
        resolved_query="What is DPR?",
        detected_entities=["DPR"],
    ))

    # Mock _run_graph and _run_vector
    coordinator._run_graph = AsyncMock(return_value=(["Fact 1"], ["c1"], None, 10.0, None))
    coordinator._run_vector = AsyncMock(return_value=([
        VectorSearchResult(chunk_id="c1", document_id="d1", paper_title="P1", section_path="S1", text="DPR text", score=0.9)
    ], 15.0, None))

    ctx = await coordinator.retrieve("What is DPR?")

    assert ctx.refinement_activated is False
    assert ctx.refined_facts_count == 0
    assert ctx.refined_chunks_count == 0
    assert "langgraph_refinement_total_ms" not in ctx.latency_ms


@pytest.mark.asyncio
async def test_coordinator_activates_refinement_on_evidence_gap(
    mock_query_engine, mock_vector_store, mock_metadata_resolver
):
    """Coordinator with enable_evidence_refinement=True invokes refiner on detected gap."""
    mock_query_engine.identify_entities_in_text.return_value = [("TargetEntity", "Method")]

    coordinator = RetrievalCoordinator(
        query_engine=mock_query_engine,
        vector_store=mock_vector_store,
        metadata_resolver=mock_metadata_resolver,
        enable_evidence_refinement=True,
    )
    coordinator.classifier = MagicMock()
    coordinator.classifier.classify = AsyncMock(return_value=RoutingResult(
        decision=RouteDecision.BOTH,
        confidence=0.95,
        reasoning="Test",
        resolved_query="Tell me about TargetEntity",
        detected_entities=["TargetEntity"],
    ))

    # Initial retrieval returns context WITHOUT TargetEntity (simulating gap)
    coordinator._run_graph = AsyncMock(return_value=(
        ["Other entity fact [chunk: c_init_1]"],
        ["c_init_1"],
        None,
        10.0,
        None,
    ))
    coordinator._run_vector = AsyncMock(return_value=([
        VectorSearchResult(chunk_id="c_init_2", document_id="doc_other", paper_title="Other Paper", section_path="S1", text="Other text", score=0.8)
    ], 15.0, None))

    ctx = await coordinator.retrieve("Tell me about TargetEntity")

    assert ctx.refinement_activated is True
    assert "TargetEntity" in ctx.missing_entities
    assert "langgraph_refinement_total_ms" in ctx.latency_ms
    # Verify provenance registration
    assert "2004_04906_001" in ctx.cited_chunk_ids  # From refined graph fact
    assert "2004_04906_002" in ctx.cited_chunk_ids  # From refined vector chunk


@pytest.mark.asyncio
async def test_coordinator_graceful_fallback_on_refiner_exception(
    mock_query_engine, mock_vector_store, mock_metadata_resolver
):
    """Coordinator catches refiner errors and returns valid unrefined context."""
    coordinator = RetrievalCoordinator(
        query_engine=mock_query_engine,
        vector_store=mock_vector_store,
        metadata_resolver=mock_metadata_resolver,
        enable_evidence_refinement=True,
    )
    coordinator.classifier = MagicMock()
    coordinator.classifier.classify = AsyncMock(return_value=RoutingResult(
        decision=RouteDecision.BOTH,
        confidence=0.9,
        reasoning="Test",
        resolved_query="What is DPR?",
        detected_entities=[],
    ))
    coordinator._run_graph = AsyncMock(return_value=(["Fact 1"], ["c1"], None, 10.0, None))
    coordinator._run_vector = AsyncMock(return_value=([], 10.0, None))

    # Force refiner to raise an unexpected runtime exception
    mock_refiner = MagicMock()
    mock_refiner.refine = AsyncMock(side_effect=RuntimeError("Simulated remote connection failure"))
    coordinator.refiner = mock_refiner

    ctx = await coordinator.retrieve("What is DPR?")

    # Query succeeds, initial context preserved, refinement logged as inactive
    assert ctx.refinement_activated is False
    assert ctx.graph_facts == ["Fact 1"]
    assert "langgraph_refinement_total_ms" in ctx.latency_ms
