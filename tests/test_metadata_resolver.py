"""
Tests for Document Metadata Resolver and Coordinator Integration.
"""

import pytest
from src.router.metadata_resolver import MetadataEvidenceRecord, MetadataResolver
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RouteDecision


def test_metadata_resolver_initialization():
    resolver = MetadataResolver()
    assert len(resolver._indexed_papers) > 0


def test_metadata_resolver_q1hop01_authors():
    resolver = MetadataResolver()
    query = "Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning?"
    records = resolver.resolve(query, detected_entities=["GraphRAG-R1"])
    assert len(records) >= 1
    rec_ids = [r.id for r in records]
    assert "meta_arxiv_2507_23581v2_authors" in rec_ids
    target = next(r for r in records if r.id == "meta_arxiv_2507_23581v2_authors")
    assert "Chuanyue Yu" in target.authors
    assert "Kuo Zhao" in target.authors
    assert "Heng Chang" in target.authors
    assert target.source == "papers.json"
    assert target.field == "authors"


def test_metadata_resolver_q1hop04_authors():
    resolver = MetadataResolver()
    query = "Who authored the component ablation study 'Dissecting Agentic RAG' for multi-hop QA?"
    records = resolver.resolve(query, detected_entities=["Dissecting Agentic RAG"])
    assert len(records) >= 1
    rec_ids = [r.id for r in records]
    assert "meta_arxiv_2606_21553v1_authors" in rec_ids
    target = next(r for r in records if r.id == "meta_arxiv_2606_21553v1_authors")
    assert "Sheroz Shaikh" in target.authors


def test_metadata_resolver_qagg04_author_citation():
    resolver = MetadataResolver()
    query = "Compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware."
    records = resolver.resolve(query, detected_entities=["HeRo", "Compact Agentic RAG"])
    assert len(records) >= 1
    rec_ids = [r.id for r in records]
    assert "meta_arxiv_2508_20324v4_authors" in rec_ids
    target = next(r for r in records if r.id == "meta_arxiv_2508_20324v4_authors")
    assert "Rikuto Kotoge" in target.authors


def test_metadata_resolver_no_trigger_on_method_query():
    resolver = MetadataResolver()
    query = "What benchmark is proposed in 'When to use Graphs in RAG' to evaluate GraphRAG models?"
    records = resolver.resolve(query, detected_entities=["GraphRAG-Bench", "GraphRAG"])
    # Asks for benchmark, not authors/venues/metadata
    assert len(records) == 0


def test_metadata_resolver_no_trigger_on_out_of_scope():
    resolver = MetadataResolver()
    query = "What is the biochemical mechanism of light-independent reactions in C4 carbon fixation?"
    records = resolver.resolve(query, detected_entities=[])
    assert len(records) == 0


@pytest.mark.asyncio
async def test_coordinator_integration_with_metadata(monkeypatch):
    coordinator = RetrievalCoordinator()
    query = "Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning?"
    
    # Mock vector store to isolate metadata resolution
    async def mock_similarity_search(*args, **kwargs):
        return []
    
    monkeypatch.setattr(coordinator.vector_store, "similarity_search", mock_similarity_search)
    
    ctx = await coordinator.retrieve(query, session_id="test_meta_session", forced_route=RouteDecision.BOTH)
    assert len(ctx.metadata_records) >= 1
    assert "meta_arxiv_2507_23581v2_authors" in ctx.cited_chunk_ids
    assert "meta_arxiv_2507_23581v2_authors" in [m.id for m in ctx.metadata_records]


def test_metadata_resolver_q2hop02_incidental_author_no_trigger():
    """Verify ADR 052: Incidental author mentions in benchmark queries without metadata intent do not trigger catalog headers."""
    resolver = MetadataResolver()
    query = "What four task categories are covered by the GraphRAG-Bench evaluation suite introduced by Zhishang Xiang et al.?"
    records = resolver.resolve(query, detected_entities=["GraphRAG-Bench", "Zhishang Xiang"])
    assert len(records) == 0


@pytest.mark.asyncio
async def test_coordinator_placeholder_author_suppression(monkeypatch):
    """Verify ADR 052: Conflicting 'Unknown Author' facts are suppressed in favor of authoritative catalog metadata."""
    coordinator = RetrievalCoordinator()
    query = "Who authored the component ablation study 'Dissecting Agentic RAG' for multi-hop QA?"
    
    # Mock graph runner to return conflicting placeholder fact
    async def mock_run_graph(*args, **kwargs):
        return (
            [
                "Paper 'Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model' was authored by Unknown Author [chunk: chunk_arxiv_2606_21553v1_000].",
                "Entity 'Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model' -[:USES_METHOD]- 'Qwen2.5-7B-Instruct' (Method) [chunk: chunk_arxiv_2606_21553v1_000].",
            ],
            {"chunk_arxiv_2606_21553v1_000"},
            10.0,
            None,
        )
    
    async def mock_similarity_search(*args, **kwargs):
        return []
        
    monkeypatch.setattr(coordinator, "_run_graph", mock_run_graph)
    monkeypatch.setattr(coordinator.vector_store, "similarity_search", mock_similarity_search)
    
    ctx = await coordinator.retrieve(query, session_id="test_suppress_session", forced_route=RouteDecision.BOTH)
    
    # Assert metadata was retrieved
    assert len(ctx.metadata_records) >= 1
    assert any(m.id == "meta_arxiv_2606_21553v1_authors" for m in ctx.metadata_records)
    
    # Assert Unknown Author was suppressed from graph_facts
    assert not any("Unknown Author" in f for f in ctx.graph_facts)
    # Assert valid relation was retained
    assert any("Qwen2.5-7B-Instruct" in f for f in ctx.graph_facts)
    
    # Assert suppression was logged in suppressed_evidence
    assert len(ctx.suppressed_evidence) == 1
    supp = ctx.suppressed_evidence[0]
    assert supp["suppressed_evidence"] is True
    assert supp["reason"] == "placeholder_conflict"
    assert supp["source_id"] == "chunk_arxiv_2606_21553v1_000"
    assert supp["authoritative_source_id"] == "meta_arxiv_2606_21553v1_authors"
