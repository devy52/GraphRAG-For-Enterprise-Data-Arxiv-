"""
Unit and Integration Tests for FastAPI REST Endpoints.

Architecture Role:
    Validates Phase 7 components:
    1. Root metadata endpoint (`GET /`).
    2. Health probe endpoint (`GET /health`) with resilient handling of offline databases.
    3. Diagnostic stats endpoint (`GET /stats`).
    4. GraphRAG query execution (`POST /query`) with schema validation, error handling,
       and dependency overrides.
"""

from typing import Generator
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pytest

from src.api.main import app
from src.api.routes import get_coordinator, get_ingestion_orchestrator, get_shared_cache, get_synthesizer
from src.api.schemas import IngestStatusResponse
from src.core.cache import QueryResponseCache
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import AnswerSynthesizer, SynthesizedAnswer
from src.synthesis.validator import CitationValidationResult
from src.vector.models import VectorSearchResult


# ==============================================================================
# Fixtures & Test Data
# ==============================================================================
@pytest.fixture
def mock_retrieval_context() -> RetrievalContext:
    """Provides a synthetic RetrievalContext for API testing."""
    return RetrievalContext(
        query="What methods extend BM25?",
        route=RouteDecision.GRAPH,
        graph_facts=["'Dense Passage Retrieval' extends 'BM25' [chunk: chunk_01]"],
        retrieved_chunks=[
            VectorSearchResult(
                chunk_id="chunk_01",
                document_id="doc_dpr_01",
                paper_title="DPR Paper",
                section_path="Intro",
                text="Dense passage retrieval builds upon sparse techniques like BM25.",
                entity_ids=["Dense Passage Retrieval", "BM25"],
                score=0.91,
            )
        ],
        cited_chunk_ids=["chunk_01"],
        latency_ms={"routing_ms": 2.5, "graph_ms": 12.0},
        subgraph={
            "nodes": [
                {"id": "Dense Passage Retrieval", "label": "Dense Passage Retrieval", "type": "Method"},
                {"id": "BM25", "label": "BM25", "type": "Method"},
            ],
            "edges": [
                {"source": "Dense Passage Retrieval", "target": "BM25", "type": "EXTENDS", "confidence": 1.0}
            ],
            "total_nodes": 2,
            "total_edges": 1,
        },
    )


@pytest.fixture
def mock_synthesized_answer() -> SynthesizedAnswer:
    """Provides a synthetic SynthesizedAnswer for API testing."""
    return SynthesizedAnswer(
        query="What methods extend BM25?",
        answer="Dense Passage Retrieval extends BM25 [chunk_01].",
        route=RouteDecision.GRAPH,
        cited_chunk_ids=["chunk_01"],
        validation_result=CitationValidationResult(
            is_valid=True,
            total_citations_found=1,
            valid_citations=["chunk_01"],
            hallucinated_citations=[],
        ),
        generation_attempts=1,
        from_cache=False,
        latency_ms={"assembly_ms": 1.0, "synthesis_ms": 15.0, "validation_ms": 0.5},
    )


@pytest.fixture
def client(
    mock_retrieval_context: RetrievalContext,
    mock_synthesized_answer: SynthesizedAnswer,
) -> Generator[TestClient, None, None]:
    """
    Creates a FastAPI TestClient with mocked coordinator and synthesizer dependencies.
    """
    mock_coordinator = MagicMock()
    mock_coordinator.retrieve = AsyncMock(return_value=mock_retrieval_context)
    mock_coordinator.warmup = AsyncMock(return_value={"neo4j": True, "postgres": True})

    # Mock health check properties
    mock_driver = MagicMock()
    mock_driver.verify_connectivity = AsyncMock()
    mock_coordinator.query_engine.writer.get_driver = AsyncMock(return_value=mock_driver)

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_coordinator.vector_store.engine = mock_engine

    mock_synthesizer = MagicMock()
    mock_synthesizer.synthesize = AsyncMock(return_value=mock_synthesized_answer)

    test_cache = QueryResponseCache(max_entries=10)

    # Apply dependency overrides
    app.dependency_overrides[get_coordinator] = lambda: mock_coordinator
    app.dependency_overrides[get_synthesizer] = lambda: mock_synthesizer
    app.dependency_overrides[get_shared_cache] = lambda: test_cache

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides after test
    app.dependency_overrides.clear()


# ==============================================================================
# Endpoint Tests
# ==============================================================================
def test_root_endpoint(client: TestClient) -> None:
    """Verifies that the root info endpoint returns valid API metadata and open access attribution."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Enterprise Hybrid GraphRAG API"
    assert data["status"] == "online"
    assert "version" in data
    assert "acknowledgments" in data
    assert "Thank you to arXiv" in data["acknowledgments"]


def test_health_endpoint_healthy(client: TestClient) -> None:
    """Verifies that the /health endpoint reports healthy when backends are mock-connected."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["neo4j_connected"] is True
    assert data["postgres_connected"] is True
    assert "timestamp" in data
    assert "boot_id" in data and len(data["boot_id"]) > 0


def test_health_endpoint_degraded() -> None:
    """Verifies that the /health endpoint handles database connectivity failures gracefully."""
    failing_coordinator = MagicMock()
    # Simulate failed Neo4j connectivity
    mock_driver = MagicMock()
    mock_driver.verify_connectivity = AsyncMock(side_effect=ConnectionError("Neo4j unreachable"))
    failing_coordinator.query_engine.writer.get_driver = AsyncMock(return_value=mock_driver)

    # Simulate failed PostgreSQL connectivity
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = ConnectionError("Postgres unreachable")
    failing_coordinator.vector_store.engine = mock_engine

    app.dependency_overrides[get_coordinator] = lambda: failing_coordinator

    with TestClient(app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["neo4j_connected"] is False
        assert data["postgres_connected"] is False
        assert "boot_id" in data and len(data["boot_id"]) > 0

    app.dependency_overrides.clear()


def test_stats_endpoint(client: TestClient) -> None:
    """Verifies that /stats returns accurate runtime cache diagnostics."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "cache_hits" in data
    assert "cache_misses" in data
    assert "cache_hit_rate" in data
    assert "cached_entries" in data
    assert "models" in data
    assert "extraction_model" in data["models"]
    assert "router_model" in data["models"]
    assert "synthesis_model" in data["models"]
    assert "embedding_model" in data["models"]
    assert "infrastructure" in data
    assert "neo4j_uri" in data["infrastructure"]
    assert "postgres_target" in data["infrastructure"]


def test_query_endpoint_success(client: TestClient) -> None:
    """
    Verifies that a valid POST /query payload returns a grounded answer with citations.
    """
    payload = {
        "query": "What methods extend BM25?",
        "session_id": "session_alpha",
        "top_k": 5,
        "use_cache": True,
    }

    response = client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "What methods extend BM25?"
    assert "Dense Passage Retrieval extends BM25 [chunk_01]." in data["answer"]
    assert data["route_taken"] == "graph"
    assert data["citations"] == ["chunk_01"]
    assert data["is_grounded"] is True
    assert data["from_cache"] is False
    assert len(data["graph_facts"]) > 0
    assert "total_request_ms" in data["latency_breakdown_ms"]
    assert "routing_ms" in data["latency_breakdown_ms"]
    assert data["subgraph"] is not None
    assert len(data["subgraph"]["nodes"]) == 2
    assert len(data["subgraph"]["edges"]) == 1


def test_query_endpoint_validation_error(client: TestClient) -> None:
    """
    Verifies that invalid payloads (e.g., empty query string) are rejected with HTTP 422.
    """
    # Empty query string violates min_length=1
    payload = {"query": ""}
    response = client.post("/query", json=payload)
    assert response.status_code == 422

    # Missing query field entirely
    response_missing = client.post("/query", json={})
    assert response_missing.status_code == 422


def test_subgraph_endpoint(client: TestClient) -> None:
    """
    Verifies that the /graph/subgraph endpoint returns a valid SubgraphResponse structure.
    """
    response = client.get("/graph/subgraph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert "total_nodes" in data
    assert "total_edges" in data


def test_ui_static_endpoint(client: TestClient) -> None:
    """
    Verifies that /ui/ serves the Material 3 index.html application layout.
    """
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "Enterprise GraphRAG" in response.text
    assert "m3-app-shell" in response.text


def test_ingest_endpoints(client: TestClient) -> None:
    """
    Verifies that POST /ingest and GET /ingest/status endpoints function correctly with mock orchestrator.
    """
    mock_orch = MagicMock()
    mock_orch.start_ingestion = AsyncMock(return_value=True)
    mock_orch.get_status = MagicMock(return_value=IngestStatusResponse(
        status="running",
        stage="harvesting",
        progress_pct=10.0,
        current_item=1,
        total_items=10,
        message="Harvesting papers...",
        logs=["Started job"],
    ))

    app.dependency_overrides[get_ingestion_orchestrator] = lambda: mock_orch
    try:
        # Happy path POST /ingest
        response = client.post("/ingest", json={"mode": "existing_corpus", "chunk_limit": 10})
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "running"
        assert data["stage"] == "harvesting"
        assert data["progress_pct"] == 10.0

        # Status polling GET /ingest/status
        res_status = client.get("/ingest/status")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "running"

        # Conflict check if already running
        mock_orch.start_ingestion = AsyncMock(return_value=False)
        conflict_res = client.post("/ingest", json={"mode": "existing_corpus"})
        assert conflict_res.status_code == 409
        assert "already currently running" in conflict_res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_ingestion_orchestrator, None)


def test_communities_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verifies that GET /graph/communities returns a valid CommunityDetectionResponse structure.
    """
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock
    from src.graph.community import CommunitySummaryRecord

    mock_detector = MagicMock()
    mock_record = CommunitySummaryRecord(
        community_id="comm_01",
        title="Dense Retrieval",
        member_count=2,
        top_entities=["DPR", "Dense Passage Retrieval"],
        summary="Research on dense neural passage retrieval.",
        themes=["Retrieval", "NLP"],
    )
    mock_detector.detect_communities = AsyncMock(return_value=[mock_record])
    monkeypatch.setattr("src.graph.community.get_community_detector", lambda: mock_detector)

    response = client.get("/graph/communities")
    assert response.status_code == 200
    data = response.json()
    assert "total_communities" in data
    assert "communities" in data
    assert "generated_at" in data
    assert data["total_communities"] == 1


def test_incremental_paper_ingest_endpoint(client: TestClient) -> None:
    """
    Verifies that POST /ingest/paper incrementally ingests a publication.
    """
    mock_orch = MagicMock()
    mock_orch.ingest_paper_incremental = AsyncMock(return_value={
        "paper_id": "paper_test_01",
        "title": "Incremental Retrieval Paper",
        "chunks_created": 3,
        "facts_written": 5,
        "entities_written": 4,
        "vectors_upserted": 3,
        "status": "success",
    })
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: mock_orch
    try:
        payload = {
            "paper_id": "paper_test_01",
            "title": "Incremental Retrieval Paper",
            "abstract": "This is a test abstract.",
            "authors": ["Alice", "Bob"],
        }
        res = client.post("/ingest/paper", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["paper_id"] == "paper_test_01"
        assert data["chunks_created"] == 3
        assert data["status"] == "success"
    finally:
        app.dependency_overrides.pop(get_ingestion_orchestrator, None)


