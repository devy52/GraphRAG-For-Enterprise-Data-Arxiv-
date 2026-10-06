"""
Vector Data Models & Search Result Schemas.

Architecture Role:
    Part of Phase 3 (Vector Store Ingestion & pgvector). Defines domain schemas for
    dense vector payload persistence (`VectorChunkRecord`) and ranked similarity retrieval
    results (`VectorSearchResult`). Used by the vector store indexer (`indexer.py`) and
    downstream hybrid query coordinator / synthesizer.

Models:
    - `VectorChunkRecord`: Data transport model for embedding batches into PostgreSQL.
    - `VectorSearchResult`: Clean, typed representation of retrieved passages with cosine
      similarity scores and associated entity mentions.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class VectorChunkRecord(BaseModel):
    """
    Represents a chunk and its dense vector embedding ready for insertion into pgvector.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier (e.g. 'chunk_arxiv_2005_11401_000')")
    document_id: str = Field(..., description="Parent document or paper identifier")
    paper_title: str = Field(..., description="Title of the paper")
    section_path: str = Field(default="Abstract", description="Section header or hierarchy path")
    text: str = Field(..., description="Raw passage text")
    chunk_index: int = Field(..., description="Index of chunk within parent document")
    embedding: List[float] = Field(..., description="Dense vector embedding representation")
    entity_ids: List[str] = Field(default_factory=list, description="Canonical entity names mentioned in this chunk")
    sha256_hash: str = Field(..., description="SHA-256 hash of text content for idempotency")


class VectorSearchResult(BaseModel):
    """
    Represents a single passage retrieved via vector similarity search.
    """
    chunk_id: str = Field(..., description="Retrieved chunk ID")
    document_id: str = Field(..., description="Parent paper ID")
    paper_title: str = Field(..., description="Title of the source paper")
    section_path: str = Field(..., description="Section of the paper")
    text: str = Field(..., description="Passage content")
    score: float = Field(..., description="Similarity score (e.g. cosine similarity 0.0 to 1.0)")
    entity_ids: List[str] = Field(default_factory=list, description="Entities associated with this chunk")
