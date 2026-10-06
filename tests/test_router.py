"""
Unit and Integration Tests for Session Memory, Route Classifier, and Retrieval Coordinator.

Architecture Role:
    Validates Phase 5 components. Ensures:
    1. Session memory maintains strict sliding-window bounds ($k=3$) and resolves pronoun coreferences.
    2. Route classifier accurately separates structural, semantic, and hybrid intents.
    3. Low-confidence classifications (< 0.70) escalate to hybrid retrieval ('both').
    4. Retrieval coordinator dispatches requests to graph/vector engines and aggregates citations.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.graph.models import EntityType
from src.graph.query_engine import GraphQueryResult
from src.graph.templates import QueryTemplateType
from src.memory.session import SessionMemory, SessionTurn
from src.router.classifier import MIN_CONFIDENCE_THRESHOLD, RouteClassifier
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RetrievalContext, RouteDecision, RoutingResult
from src.vector.models import VectorSearchResult


# ==============================================================================
# Fixtures & Test Data
# ==============================================================================
@pytest.fixture
def session_memory() -> SessionMemory:
    """Provides a fresh SessionMemory instance with default window size k=3."""
    return SessionMemory(window_size=3)


@pytest.fixture
def mock_graph_engine() -> MagicMock:
    """Mocks GraphQueryEngine returning deterministic GraphQueryResult."""
    engine = MagicMock()
    # Mock identify_entities_in_text
    engine.identify_entities_in_text.return_value = [("Dense Passage Retrieval", EntityType.METHOD)]
    # Mock detect_best_template
    engine.detect_best_template.return_value = (
        QueryTemplateType.METHOD_ANCESTRY_EXTENDS,
        {"method_name": "Dense Passage Retrieval"},
    )
    # Mock async query
    mock_result = GraphQueryResult(
        template_type=QueryTemplateType.METHOD_ANCESTRY_EXTENDS,
        parameters={"method_name": "Dense Passage Retrieval"},
        raw_records=[{"ancestor_name": "BM25", "source_chunk_id": "chunk_ancestor_01"}],
        formatted_statements=["'Dense Passage Retrieval' extends 'BM25' [chunk: chunk_ancestor_01]"],
        source_chunk_ids=["chunk_ancestor_01"],
        latency_ms=12.5,
    )
    engine.query = AsyncMock(return_value=mock_result)
    return engine


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Mocks VectorStore returning sample VectorSearchResult list."""
    store = MagicMock()
    mock_chunks = [
        VectorSearchResult(
            chunk_id="chunk_vec_01",
            document_id="doc_dpr_01",
            paper_title="Dense Passage Retrieval for Open-Domain Question Answering",
            section_path="Abstract",
            text="We show that retrieval can be practically implemented using dense representations.",
            entity_ids=["Dense Passage Retrieval", "BM25"],
            score=0.92,
        ),
        VectorSearchResult(
            chunk_id="chunk_vec_02",
            document_id="doc_dpr_01",
            paper_title="Dense Passage Retrieval for Open-Domain Question Answering",
            section_path="Experiments",
            text="On Natural Questions, DPR outperforms BM25 by a wide margin.",
            entity_ids=["Dense Passage Retrieval", "Natural Questions"],
            score=0.88,
        ),
    ]
    store.similarity_search = AsyncMock(return_value=mock_chunks)
    store.get_document_ids_for_entities = AsyncMock(return_value=["doc_dpr_01"])
    return store


# ==============================================================================
# Unit Tests: Session Memory & Coreference Resolution
# ==============================================================================
def test_session_memory_sliding_window_enforcement(session_memory: SessionMemory) -> None:
    """
    Verifies that the session memory strictly bounds retained messages to 2 * window_size (6 turns).
    """
    # Step 1: Add 5 interaction turn pairs (10 messages total)
    for i in range(1, 6):
        session_memory.add_user_turn(f"User query turn {i}", entities=[f"Entity_{i}"])
        session_memory.add_assistant_turn(f"Assistant response turn {i}")

    # Step 2: Verify total retained turns is clamped to window_size * 2 (3 * 2 = 6)
    assert len(session_memory.turns) == 6, f"Expected 6 retained turns, got {len(session_memory.turns)}"

    # Step 3: Verify that oldest turns (1 and 2) were evicted
    retained_texts = [t.text for t in session_memory.turns]
    assert "User query turn 1" not in retained_texts
    assert "User query turn 2" not in retained_texts
    assert "User query turn 5" in retained_texts


def test_session_memory_coreference_resolution(session_memory: SessionMemory) -> None:
    """
    Verifies rule-based coreference resolution replaces ambiguous pronouns with the latest entity.
    """
    # Step 1: Record dialogue mentioning 'Retrieval-Augmented Generation'
    session_memory.add_user_turn("Tell me about Retrieval-Augmented Generation", entities=["Retrieval-Augmented Generation"])
    session_memory.add_assistant_turn("RAG is a hybrid parametric-nonparametric paradigm.")

    # Step 2: Test ambiguous pronoun replacement
    query_1 = "What datasets did it use?"
    resolved_1 = session_memory.resolve_coreference(query_1)
    assert "Retrieval-Augmented Generation" in resolved_1
    assert "it" not in resolved_1.lower().split()

    # Step 3: Test demonstrative phrase replacement
    query_2 = "Who wrote that paper?"
    resolved_2 = session_memory.resolve_coreference(query_2)
    assert "'Retrieval-Augmented Generation'" in resolved_2


# ==============================================================================
# Unit Tests: Intent Route Classifier
# ==============================================================================
@pytest.mark.asyncio
async def test_route_classifier_relational_to_graph(mock_graph_engine: MagicMock) -> None:
    """
    Verifies relational and topological queries are routed to 'graph' with high confidence.
    """
    classifier = RouteClassifier(query_engine=mock_graph_engine, use_llm=False)

    queries = [
        "Who co-authored papers with Patrick Lewis?",
        "Which papers cite the DPR paper?",
        "What methods extend Dense Passage Retrieval?",
    ]

    for q in queries:
        result = await classifier.classify(q)
        assert result.decision == RouteDecision.GRAPH, f"Expected GRAPH for '{q}', got {result.decision}"
        assert result.confidence >= MIN_CONFIDENCE_THRESHOLD


@pytest.mark.asyncio
async def test_route_classifier_semantic_to_vector() -> None:
    """
    Verifies semantic explanation and conceptual overview queries route to 'vector'.
    """
    # Use empty query engine with no registered entities
    empty_engine = MagicMock()
    empty_engine.identify_entities_in_text.return_value = []
    empty_engine.detect_best_template.return_value = None

    classifier = RouteClassifier(query_engine=empty_engine, use_llm=False)

    queries = [
        "Summarize the key architectural innovations of Dense Passage Retrieval.",
        "Explain the mathematical intuition behind the dual-encoder contrastive loss function.",
        "Describe the document chunking strategy used in the experiments.",
    ]

    for q in queries:
        result = await classifier.classify(q)
        assert result.decision == RouteDecision.VECTOR, f"Expected VECTOR for '{q}', got {result.decision}"
        assert result.confidence >= MIN_CONFIDENCE_THRESHOLD


@pytest.mark.asyncio
async def test_route_classifier_hybrid_and_escalation() -> None:
    """
    Verifies multifaceted queries route to 'both', and ambiguous queries escalate to 'both'.
    """
    empty_engine = MagicMock()
    empty_engine.identify_entities_in_text.return_value = []
    empty_engine.detect_best_template.return_value = None

    classifier = RouteClassifier(query_engine=empty_engine, use_llm=False)

    # 1. Multi-faceted hybrid query (both relational and semantic cues)
    hybrid_query = "Which methods evaluate on HotpotQA and explain why they achieve higher accuracy?"
    result_hybrid = await classifier.classify(hybrid_query)
    assert result_hybrid.decision == RouteDecision.BOTH
    assert result_hybrid.confidence >= MIN_CONFIDENCE_THRESHOLD

    # 2. Ambiguous query with no strong signals -> low confidence must escalate to 'both'
    ambiguous_query = "Tell me something interesting about accuracy."
    result_ambiguous = await classifier.classify(ambiguous_query)
    assert result_ambiguous.decision == RouteDecision.BOTH, "Low confidence query must escalate to BOTH"


@pytest.mark.asyncio
async def test_route_classifier_llm_mocked() -> None:
    """
    Verifies LLM-based classification, JSON parsing, and confidence escalation using a mocked client.
    """
    mock_llm = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"route": "graph", "confidence": 0.95, "reasoning": "Lineage query"}'
    mock_response = MagicMock(choices=[mock_choice])
    mock_llm.chat.completions.create = AsyncMock(return_value=mock_response)

    classifier = RouteClassifier(use_llm=True, llm_client=mock_llm)
    result = await classifier.classify("What methods extend DPR?")
    assert result.decision == RouteDecision.GRAPH
    assert result.confidence == 0.95

    # Test low confidence escalation (< 0.70 -> BOTH)
    mock_choice.message.content = '{"route": "vector", "confidence": 0.55, "reasoning": "Uncertain"}'
    result_esc = await classifier.classify("Some vague question")
    assert result_esc.decision == RouteDecision.BOTH
    assert "Escalated to 'both'" in result_esc.reasoning


# ==============================================================================
# Integration Tests: Retrieval Coordinator
# ==============================================================================
@pytest.mark.asyncio
async def test_retrieval_coordinator_end_to_end(
    mock_graph_engine: MagicMock,
    mock_vector_store: MagicMock,
) -> None:
    """
    Verifies RetrievalCoordinator dispatches across graph, vector, and hybrid routes,
    aggregating citations and tracking sub-operation latencies.
    """
    coordinator = RetrievalCoordinator(
        classifier=RouteClassifier(query_engine=mock_graph_engine, use_llm=False),
        query_engine=mock_graph_engine,
        vector_store=mock_vector_store,
    )

    # Turn 1: Structural query -> RouteDecision.GRAPH
    ctx_graph = await coordinator.retrieve(
        query="What methods extend Dense Passage Retrieval?",
        session_id="session_test_01",
    )
    assert ctx_graph.route == RouteDecision.GRAPH
    assert len(ctx_graph.graph_facts) > 0
    assert "chunk_ancestor_01" in ctx_graph.cited_chunk_ids
    assert "routing_ms" in ctx_graph.latency_ms
    assert "graph_ms" in ctx_graph.latency_ms

    # Turn 2: Coreference follow-up query with pronoun -> "Explain its contrastive loss"
    # Should resolve "its" to "Dense Passage Retrieval" and route to VECTOR
    ctx_vector = await coordinator.retrieve(
        query="Explain its contrastive loss function",
        session_id="session_test_01",
    )
    assert "Dense Passage Retrieval" in ctx_vector.query
    assert ctx_vector.route == RouteDecision.VECTOR
    assert len(ctx_vector.retrieved_chunks) > 0
    assert "chunk_vec_01" in ctx_vector.cited_chunk_ids
    assert "vector_ms" in ctx_vector.latency_ms

    # Turn 3: Multifaceted hybrid query -> RouteDecision.BOTH
    ctx_hybrid = await coordinator.retrieve(
        query="Which methods evaluate on HotpotQA and explain why they achieve higher recall?",
        session_id="session_test_01",
    )
    assert ctx_hybrid.route == RouteDecision.BOTH
    # Should combine both graph statements and vector chunks
    assert len(ctx_hybrid.graph_facts) > 0
    assert len(ctx_hybrid.retrieved_chunks) > 0
    # Cited chunk IDs must include IDs from both graph and vector
    assert "chunk_ancestor_01" in ctx_hybrid.cited_chunk_ids
    assert "chunk_vec_01" in ctx_hybrid.cited_chunk_ids
    assert "chunk_vec_02" in ctx_hybrid.cited_chunk_ids


@pytest.mark.asyncio
async def test_retrieval_coordinator_warmup(
    mock_graph_engine: MagicMock,
    mock_vector_store: MagicMock,
) -> None:
    """
    Verifies that coordinator.warmup() exercises both database drivers and returns status.
    """
    mock_driver = MagicMock()
    mock_driver.verify_connectivity = AsyncMock()
    mock_graph_engine.writer.get_driver = AsyncMock(return_value=mock_driver)

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_vector_store.engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_vector_store.engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_vector_store.initialize = AsyncMock()

    coordinator = RetrievalCoordinator(
        query_engine=mock_graph_engine,
        vector_store=mock_vector_store,
    )

    status = await coordinator.warmup()
    assert status["neo4j"] is True
    assert status["postgres"] is True
    mock_driver.verify_connectivity.assert_awaited_once()
    mock_vector_store.initialize.assert_awaited_once()
