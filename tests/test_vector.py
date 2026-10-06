"""
Unit Tests for Vector Store Models, Embedding Generator, and pgvector Schema.

Architecture Role:
    Validates Phase 3 (Vector Store Ingestion & pgvector). Verifies data schemas (`VectorChunkRecord`,
    `VectorSearchResult`), deterministic unit vector mock generation for offline environments, and
    SQLAlchemy ORM table mapping for `document_chunks`.

Invariants Tested:
    1. `VectorChunkRecord` attribute integrity, vector dimension (1536), and metadata storage.
    2. `VectorSearchResult` score bounds and property preservation.
    3. `EmbeddingGenerator` deterministic fallback generating normalized unit vectors (L2 norm = 1.0).
    4. `DocumentChunkModel` SQLAlchemy ORM table name and column mapping integrity.
"""

import pytest

from src.vector.indexer import EmbeddingGenerator
from src.vector.models import VectorChunkRecord, VectorSearchResult
from src.vector.schema import DocumentChunkModel


def test_vector_chunk_record_validation() -> None:
    """
    Test Objective:
        Verify `VectorChunkRecord` instantiation, embedding dimension validation, and metadata types.

    Assertions:
        - `chunk_id` is preserved.
        - Embedding vector has length matching the expected 1536 dimensions.
        - `entity_ids` retains list of recognized canonical entities.
    """
    # Step 1: Instantiate sample VectorChunkRecord with 1536-dim embedding
    record = VectorChunkRecord(
        chunk_id="chunk_arxiv_2005_11401_000",
        document_id="arxiv_2005.11401",
        paper_title="Retrieval-Augmented Generation",
        section_path="Abstract",
        text="Dense passage retrieval combines dual-encoders.",
        chunk_index=0,
        embedding=[0.1] * 1536,
        entity_ids=["RAG", "DPR"],
        sha256_hash="mock_hash_12345",
    )

    # Step 2: Assert attributes and vector length
    assert record.chunk_id == "chunk_arxiv_2005_11401_000"
    assert len(record.embedding) == 1536
    assert record.entity_ids == ["RAG", "DPR"]


def test_vector_search_result_scoring() -> None:
    """
    Test Objective:
        Verify that `VectorSearchResult` correctly maintains cosine similarity scores and passage fields.

    Assertions:
        - `score` matches cosine similarity float value.
        - `chunk_id` correctly associates with source passage.
    """
    # Step 1: Create sample search result model
    result = VectorSearchResult(
        chunk_id="chunk_001",
        document_id="doc_001",
        paper_title="Dense Retrieval",
        section_path="Methodology",
        text="Sample passage text.",
        score=0.92,
        entity_ids=["Methodology"],
    )

    # Step 2: Assert score and identifier fields
    assert result.score == 0.92
    assert result.chunk_id == "chunk_001"


def test_embedding_generator_deterministic_fallback() -> None:
    """
    Test Objective:
        Verify that `EmbeddingGenerator._generate_mock_embedding` produces deterministic,
        1536-dimensional unit vectors with an L2 norm of 1.0 when running offline.

    Assertions:
        - Generated vector length is exactly 1536.
        - Identical text inputs produce identical vectors.
        - Different text inputs produce distinct vectors.
        - Vector L2 norm is equal to 1.0 (within float precision).
    """
    # Step 1: Initialize EmbeddingGenerator instance
    generator = EmbeddingGenerator()

    # Step 2: Generate mock vectors for identical and distinct text inputs
    vec1 = generator._generate_mock_embedding("Retrieval-Augmented Generation")
    vec2 = generator._generate_mock_embedding("Retrieval-Augmented Generation")
    vec3 = generator._generate_mock_embedding("Different text query")

    # Step 3: Assert dimension and determinism
    assert len(vec1) == generator.dimension
    assert vec1 == vec2  # Deterministic for identical inputs
    assert vec1 != vec3  # Distinct for different inputs

    # Step 4: Verify mathematical normalization: L2 norm = sqrt(sum(x^2)) == 1.0
    norm = sum(x * x for x in vec1) ** 0.5
    assert abs(norm - 1.0) < 1e-5


def test_document_chunk_model_table_schema() -> None:
    """
    Test Objective:
        Verify that the SQLAlchemy ORM `DocumentChunkModel` defines the required
        pgvector column structure and table name.

    Assertions:
        - Table name is 'document_chunks'.
        - Key columns ('chunk_id', 'document_id', 'embedding', 'entity_ids', 'sha256_hash') exist.
    """
    # Step 1: Verify ORM table name
    assert DocumentChunkModel.__tablename__ == "document_chunks"

    # Step 2: Verify mapped column names
    columns = [c.name for c in DocumentChunkModel.__table__.columns]
    assert "chunk_id" in columns
    assert "document_id" in columns
    assert "embedding" in columns
    assert "entity_ids" in columns
    assert "sha256_hash" in columns
