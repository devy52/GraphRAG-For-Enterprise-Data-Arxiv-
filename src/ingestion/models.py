"""
Data Models for Paper Ingestion, Metadata Representation, and Document Chunking.

Architecture Role:
    Part of Phase 1 (Ingestion). Defines the fundamental data exchange models between
    the external paper collectors (`collector.py`), the text chunker (`chunker.py`),
    the knowledge graph extraction pipeline (`extractor.py`), and the dense vector store (`indexer.py`).

Models:
    - `Author`: Encapsulates researcher names and academic/corporate affiliations.
    - `Paper`: Complete scientific publication with abstract, authors, venue, and citation graph links.
    - `DocumentChunk`: Discrete text passage with deterministic hashing and hierarchy metadata.
      Serves as the shared reference unit linking graph edges, vector records, and citations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Author(BaseModel):
    """
    Represents an author of a scientific or enterprise publication.
    """
    name: str = Field(..., description="Full canonical name of the author")
    affiliation: Optional[str] = Field(default=None, description="Author's primary institution or affiliation")


class Paper(BaseModel):
    """
    Represents an ingested scientific paper with full metadata and citation graph links.
    """
    paper_id: str = Field(..., description="Unique canonical paper identifier (e.g. arXiv ID or Semantic Scholar ID)")
    title: str = Field(..., description="Title of the paper")
    abstract: str = Field(default="", description="Abstract text of the paper")
    authors: List[Author] = Field(default_factory=list, description="List of paper authors")
    published_year: Optional[int] = Field(default=None, description="Publication year")
    venue: Optional[str] = Field(default=None, description="Conference, journal, or preprint server name")
    arxiv_id: Optional[str] = Field(default=None, description="arXiv accession ID if available")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier")
    citation_count: int = Field(default=0, description="Total number of known citations")
    references: List[str] = Field(default_factory=list, description="List of paper IDs or titles referenced by this paper")
    citations: List[str] = Field(default_factory=list, description="List of paper IDs citing this paper")
    full_text: Optional[str] = Field(default=None, description="Optional raw or full body text of the paper")


class DocumentChunk(BaseModel):
    """
    Represents a discrete text chunk produced from a document.
    
    Serves as the universal bridge linking:
    1. Knowledge graph edges (via source_chunk_id).
    2. pgvector embeddings (via chunk_id).
    3. Grounded citation validation in API responses.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier (e.g. chunk_arxiv_2005_11401_000)")
    document_id: str = Field(..., description="Parent paper or document ID")
    paper_title: str = Field(..., description="Title of the parent document for context")
    section_path: str = Field(default="Abstract", description="Section or hierarchy header (e.g. '3.2 Model Architecture')")
    text: str = Field(..., description="Raw text content of the chunk")
    chunk_index: int = Field(..., description="0-indexed position of chunk in parent document")
    character_count: int = Field(..., description="Length of chunk text in characters")
    sha256_hash: str = Field(..., description="SHA-256 hash of text content for idempotent caching")


class IngestRequest(BaseModel):
    """Request payload to trigger asynchronous corpus ingestion."""
    mode: str = Field("existing_corpus", description="Ingestion mode: 'existing_corpus' or 'harvest_arxiv'")
    query: str = Field("retrieval-augmented generation", description="arXiv query search term if harvesting")
    paper_limit: int = Field(50, ge=1, le=200, description="Max papers to fetch from arXiv")
    chunk_limit: Optional[int] = Field(None, ge=1, description="Optional cap on number of chunks to process")
    populate_neo4j: bool = Field(True, description="Whether to run LLM extraction and Neo4j writing")
    populate_pgvector: bool = Field(True, description="Whether to embed and index into pgvector")
    reset_checkpoint: bool = Field(False, description="Whether to discard existing checkpoint and reprocess from chunk 0")
    incremental: bool = Field(True, description="Whether to run hash-based incremental delta ingestion skipping unchanged chunks")



class IngestStatusResponse(BaseModel):
    """Status payload tracking the active or most recent asynchronous ingestion run."""
    status: str = Field(..., description="Status: 'idle', 'running', 'completed', or 'failed'")
    stage: str = Field(..., description="Active pipeline stage (e.g. 'harvesting', 'chunking', 'extracting')")
    progress_pct: float = Field(0.0, ge=0.0, le=100.0, description="Percentage of progress completed (0.0 to 100.0)")
    current_item: int = Field(0, description="Index/count of item currently being processed")
    total_items: int = Field(0, description="Total items expected in the current stage")
    message: str = Field("", description="Human-readable status summary")
    logs: List[str] = Field(default_factory=list, description="Recent circular log messages from the ingestion runner")

