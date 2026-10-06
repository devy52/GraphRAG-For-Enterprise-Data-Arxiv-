"""
Unit Tests for Ingestion Pipeline, Paper Models, and Document Chunker.

Architecture Role:
    Validates Phase 1 (Ingestion). Ensures that scientific document models (`Author`, `Paper`),
    recursive boundary-aligned chunking (`DocumentChunker`), deterministic SHA-256 digests,
    and arXiv rate-limit collector configs adhere to system specifications.

Invariants Tested:
    1. Paper and Author model instantiation and field validation.
    2. Chunker boundary preservation, deterministic chunk IDs (`chunk_{sanitized_id}_{idx:03d}`).
    3. Determinism of SHA-256 hash digests across identical text inputs.
    4. Collector settings initialization and polite >= 3.0s throttling policy compliance.
"""

import pytest

from src.ingestion.chunker import DocumentChunker
from src.ingestion.collector import PaperCollector
from src.ingestion.models import Author, DocumentChunk, IngestRequest, Paper


def test_paper_model_validation() -> None:
    """
    Test Objective:
        Verify that `Paper` and `Author` Pydantic models validate nested structures,
        citation links, and publication years correctly.

    Assertions:
        - `paper_id` is preserved accurately.
        - `Author` objects are correctly parsed into the `authors` list.
        - Reference and citation ID collections maintain element counts.
    """
    # Step 1: Create sample Author domain model
    author = Author(name="Patrick Lewis", affiliation="Meta AI")

    # Step 2: Instantiate Paper model with authors, references, and citations
    paper = Paper(
        paper_id="2005.11401",
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        abstract="We explore models that combine pre-trained parametric memory with non-parametric memory.",
        authors=[author],
        published_year=2020,
        venue="NeurIPS",
        references=["ref_001", "ref_002"],
        citations=["cite_001"],
    )

    # Step 3: Assert field validations
    assert paper.paper_id == "2005.11401"
    assert len(paper.authors) == 1
    assert paper.authors[0].name == "Patrick Lewis"
    assert len(paper.references) == 2


def test_document_chunker_splitting() -> None:
    """
    Test Objective:
        Verify that `DocumentChunker` splits raw paper text into boundary-aligned `DocumentChunk`
        records with deterministic identifiers and SHA-256 hashes.

    Assertions:
        - Generated items are instances of `DocumentChunk`.
        - Chunk IDs follow the structured format `chunk_{clean_id}_{index:03d}`.
        - Sliced text lengths stay within expected bounds.
        - SHA-256 hash length is exactly 64 characters (hex digest).
    """
    # Step 1: Configure chunker with test window parameters
    chunker = DocumentChunker(chunk_size=200, chunk_overlap=30)
    sample_text = (
        "Retrieval-Augmented Generation (RAG) combines dense vector retrieval with "
        "generative language models. By retrieving documents from a dense index, "
        "the model conditions generation on explicit factual knowledge. This drastically "
        "reduces hallucination and improves factual grounding on open-domain QA tasks."
    )
    paper = Paper(
        paper_id="arxiv:2005.11401",
        title="RAG Paper",
        abstract=sample_text,
    )

    # Step 2: Execute chunking on paper
    chunks = chunker.chunk_paper(paper)
    
    # Step 3: Assert chunk attributes and formatting invariants
    assert len(chunks) >= 1
    for i, chunk in enumerate(chunks):
        assert isinstance(chunk, DocumentChunk)
        assert chunk.document_id == "arxiv:2005.11401"
        assert chunk.chunk_id == f"chunk_arxiv_2005_11401_{i:03d}"
        assert len(chunk.text) <= 250  # Boundary check with tolerance
        assert len(chunk.sha256_hash) == 64  # Valid SHA-256 hexadecimal length


def test_chunker_hash_determinism() -> None:
    """
    Test Objective:
        Verify that `DocumentChunker.compute_sha256` produces exact identical digests
        for identical text inputs across independent executions.

    Assertions:
        - `hash1 == hash2` for identical inputs.
    """
    # Step 1: Define invariant test string
    text = "Dense passage retrieval utilizes dual-encoder architectures."

    # Step 2: Compute hashes independently
    hash1 = DocumentChunker.compute_sha256(text)
    hash2 = DocumentChunker.compute_sha256(text)

    # Step 3: Assert equality
    assert hash1 == hash2


def test_collector_initialization() -> None:
    """
    Test Objective:
        Verify that `PaperCollector` loads configuration settings and enforces arXiv rate limits.

    Assertions:
        - `arxiv_delay_seconds` is >= 3.0 seconds to comply with arXiv API terms of service.
        - `arxiv_user_agent` contains the project identifier.
    """
    # Step 1: Initialize collector instance
    collector = PaperCollector()

    # Step 2: Verify compliance parameters
    assert collector.settings.arxiv_delay_seconds >= 3.0
    assert "Enterprise-GraphRAG" in collector.settings.arxiv_user_agent


def test_ingest_request_schema() -> None:
    """
    Test Objective:
        Verify that IngestRequest initializes with default parameters and allows reset_checkpoint.
    """
    req = IngestRequest()
    assert req.mode == "existing_corpus"
    assert req.populate_neo4j is True
    assert req.populate_pgvector is True
    assert req.reset_checkpoint is False

    custom_req = IngestRequest(reset_checkpoint=True)
    assert custom_req.reset_checkpoint is True


def test_orchestrator_checkpointing(monkeypatch, tmp_path) -> None:
    """
    Test Objective:
        Verify that IngestionOrchestrator correctly loads, saves, and clears
        checkpoint state from disk.
    """
    from src.ingestion.orchestrator import IngestionOrchestrator
    import src.ingestion.orchestrator as orch_module

    # Redirect checkpoint path to tmp_path
    test_cp = str(tmp_path / "test_checkpoint.json")
    monkeypatch.setattr(orch_module, "CHECKPOINT_FILE", test_cp)

    # 1. Initial load should return empty set
    initial = IngestionOrchestrator._load_checkpoint()
    assert initial == set()

    # 2. Save 2 chunks
    IngestionOrchestrator._save_checkpoint({"chunk_001", "chunk_002"}, total_facts=5)
    loaded = IngestionOrchestrator._load_checkpoint()
    assert loaded == {"chunk_001", "chunk_002"}

    # 3. Clear checkpoint
    IngestionOrchestrator._clear_checkpoint()
    assert IngestionOrchestrator._load_checkpoint() == set()


@pytest.mark.asyncio
async def test_incremental_delta_detection_skips_unchanged(monkeypatch, tmp_path) -> None:
    """
    Test Objective:
        Verify that IngestionOrchestrator in incremental mode skips chunks whose
        SHA-256 hashes match existing records in PostgreSQL.
    """
    from unittest.mock import AsyncMock, MagicMock
    from src.ingestion.orchestrator import IngestionOrchestrator
    import src.ingestion.orchestrator as orch_module

    # Mock chunks
    c1 = DocumentChunk(
        chunk_id="chunk_01",
        document_id="doc_1",
        paper_title="Title 1",
        text="Content 1",
        chunk_index=0,
        character_count=9,
        sha256_hash="hash_unchanged",
    )
    c2 = DocumentChunk(
        chunk_id="chunk_02",
        document_id="doc_1",
        paper_title="Title 1",
        text="Content 2 new",
        chunk_index=1,
        character_count=13,
        sha256_hash="hash_new",
    )

    # Mock VectorStore
    mock_store = AsyncMock()
    mock_store.initialize = AsyncMock()
    mock_store.get_existing_hashes = AsyncMock(return_value={"chunk_01": "hash_unchanged"})
    mock_store.insert_chunks = AsyncMock(return_value=1)
    mock_store.delete_chunks = AsyncMock(return_value=0)
    mock_store.close = AsyncMock()

    orchestrator = IngestionOrchestrator()
    req = IngestRequest(mode="existing_corpus", incremental=True, populate_neo4j=False, populate_pgvector=True)

    # Write mock chunks to temp corpus
    test_corpus = tmp_path / "chunks.json"
    import json
    import os
    test_corpus.write_text(json.dumps([c1.model_dump(), c2.model_dump()]), encoding="utf-8")

    orig_exists = os.path.exists
    import builtins
    orig_open = builtins.open
    monkeypatch.setattr("os.path.exists", lambda path: True if "chunks.json" in str(path) else orig_exists(path))
    monkeypatch.setattr("builtins.open", lambda p, *args, **kwargs: orig_open(test_corpus, *args, **kwargs) if "chunks.json" in str(p) else orig_open(p, *args, **kwargs))

    with monkeypatch.context() as m:
        m.setattr("src.vector.indexer.VectorStore", lambda: mock_store)
        await orchestrator._run_pipeline(req)

    # Vector store insert_chunks should only be called with c2 (the delta chunk)!
    assert mock_store.insert_chunks.called
    call_args = mock_store.insert_chunks.call_args[0][0]
    assert len(call_args) == 1
    assert call_args[0].chunk_id == "chunk_02"
    assert orchestrator.status == "completed"


