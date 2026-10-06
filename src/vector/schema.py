"""
PostgreSQL & pgvector Table Schema Definition.

Architecture Role:
    Part of Phase 3 (Vector Store Ingestion). Defines the SQLAlchemy ORM declarative model
    for the `document_chunks` table in PostgreSQL. Supports 1536-dimensional dense embeddings
    using the `pgvector` extension and provides structured column metadata for hybrid retrieval.

Inputs:
    - Embedding dimension from `src.core.config.get_settings().embedding_dimension` (1536).
    - Async SQLAlchemy engine connection.

Outputs:
    - Initialized PostgreSQL table `document_chunks` with `vector` extension enabled.

Table Structure:
    - `chunk_id`: Primary key (e.g. 'chunk_arxiv_2005_11401_000').
    - `document_id`: Source paper identifier.
    - `paper_title`: Publication title.
    - `section_path`: Section location ('Abstract', 'Methods', 'Results').
    - `text`: Raw textual passage.
    - `chunk_index`: Integer ordering index within source paper.
    - `embedding`: Vector(1536) column for cosine similarity indexing.
    - `entity_ids`: JSON list of recognized entity names mapped to this chunk.
    - `sha256_hash`: Content hash for deduplication.
    - `created_at`: Timestamp with timezone.
"""

from typing import Any, Dict, List
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.core.config import get_settings
from src.core.logging import setup_logger

logger = setup_logger(name="vector.schema")


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""
    pass


class DocumentChunkModel(Base):
    """
    SQLAlchemy ORM model for the 'document_chunks' table in PostgreSQL.
    Stores chunk text, metadata, and 2048-dimensional dense embedding vectors.
    """
    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    document_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    paper_title: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str] = mapped_column(String(256), nullable=False, default="Abstract")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(get_settings().embedding_dimension), nullable=False)
    entity_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


async def init_vector_db(engine: AsyncEngine) -> None:
    """
    Initializes PostgreSQL for vector operations:
    1. Executes 'CREATE EXTENSION IF NOT EXISTS vector' to activate pgvector types and operators.
    2. Runs synchronous table creation via Base.metadata.create_all.
    """
    async with engine.begin() as conn:
        # Step 1: Enable the pgvector extension if not already present
        logger.info("Enabling PostgreSQL 'vector' extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # Step 2: Create document_chunks and any other declared ORM tables
        logger.info("Creating database tables if not exist...")
        await conn.run_sync(Base.metadata.create_all)

    logger.info("PostgreSQL pgvector schema initialized successfully.")
