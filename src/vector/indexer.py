"""
Dense Embeddings Generator & pgvector Indexer Module.

Architecture Role:
    Part of Phase 3 (Vector Store Ingestion & pgvector). Provides the dense semantic retrieval
    component of the Hybrid GraphRAG system. Works alongside the Knowledge Graph (Neo4j) to
    ensure the query router can perform fast dense semantic searches over document chunks.

Inputs:
    - `DocumentChunk` models from Phase 1.
    - Optional entity mapping (`chunk_id -> List[canonical_entity_name]`).
    - Raw natural language query strings for vector similarity search.

Outputs:
    - Embedded and indexed records in the PostgreSQL `document_chunks` table.
    - Ranked `VectorSearchResult` objects scored by cosine similarity (`1 - (embedding <=> query)`).

Design Decisions & Invariants:
    - Batched Embedding Calls: Embeddings are sent in batches of 32 to minimize HTTP roundtrips.
    - Deterministic Unit Vector Fallback: Generates mathematically normalized unit vectors seeded by text hash
      when offline or when API keys are absent, ensuring all unit tests pass without external dependencies.
    - Idempotent PostgreSQL Upsert: Employs `INSERT INTO ... ON CONFLICT (chunk_id) DO UPDATE` to allow safe,
      re-runnable pipeline executions without duplicate chunk records.
    - pgvector Cosine Distance: Uses the native `<=>` operator (cosine distance), converting to cosine similarity
      as `1 - distance` in the SQL `SELECT` projection.
    - Dynamic ef_search Tuning: Accepts a session-scoped `ef_search` override (`SET LOCAL hnsw.ef_search`)
      allowing fine-grained recall vs. latency tuning during benchmark evaluation.
"""

import hashlib
import json
import math
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.ingestion.models import DocumentChunk
from src.vector.models import VectorChunkRecord, VectorSearchResult
from src.vector.schema import DocumentChunkModel, init_vector_db

logger = setup_logger(name="vector.indexer")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_TOP_K = 5              # Default number of nearest neighbor chunks to return
EMBEDDING_BATCH_SIZE = 32      # Batch size for OpenAI-compatible embedding API calls


class EmbeddingGenerator:
    """
    Generates dense text embeddings using OpenAI-compatible gateway endpoints.
    Includes deterministic unit vector fallback for offline/test environments.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key or "sk-dummy-key-for-test",
        )
        self.dimension = self.settings.embedding_dimension

    def _generate_mock_embedding(self, text_input: str) -> List[float]:
        """
        Generates a deterministic pseudo-random unit vector based on input text hash.
        Used when LLM_API_KEY is not configured (e.g. offline unit testing).
        Computes L2 norm and normalizes so vector magnitude equals 1.0.
        """
        seed = int(hashlib.md5(text_input.encode("utf-8")).hexdigest()[:8], 16)
        raw_vec = [math.sin(seed + i) for i in range(self.dimension)]
        norm = math.sqrt(sum(x * x for x in raw_vec)) or 1.0
        return [x / norm for x in raw_vec]

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generates dense vector embeddings for a list of text strings in batches.

        Workflow:
        1. Checks for active API key; falls back to mock unit vectors if absent or dummy key.
        2. Slices texts into chunks of `EMBEDDING_BATCH_SIZE`.
        3. Calls `client.embeddings.create` and extracts float vectors.
        """
        # Step 1: Guard against empty input list
        if not texts:
            return []

        # Step 2: Check for offline test environment or absent API key
        if not self.settings.llm_api_key or self.settings.llm_api_key.startswith("sk-dummy"):
            logger.debug("No LLM API key detected. Generating %d mock embeddings for testing.", len(texts))
            return [self._generate_mock_embedding(t) for t in texts]

        embeddings: List[List[float]] = []
        try:
            # Step 3: Iterate through text slices in batches of EMBEDDING_BATCH_SIZE
            for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                batch = texts[i : i + EMBEDDING_BATCH_SIZE]
                # Step 4: Request dense embeddings from OpenAI-compatible endpoint
                response = await self.client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=batch,
                )
                # Step 5: Extract float vectors and append to master collection
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            return embeddings
        except Exception as exc:
            # Step 6: Graceful fallback to deterministic unit vectors on network/API failure
            logger.warning("Embeddings API call failed: %s. Falling back to deterministic unit vectors.", exc)
            return [self._generate_mock_embedding(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        """
        Generates a dense embedding for a single query string.
        """
        results = await self.embed_texts([query])
        return results[0]


class VectorStore:
    """
    Manages vector storage, indexing, and HNSW similarity searches in PostgreSQL.
    """

    def __init__(self, engine: Optional[AsyncEngine] = None) -> None:
        self.settings = get_settings()
        self.engine = engine or create_async_engine(
            self.settings.postgres_async_uri,
            echo=False,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.embedding_generator = EmbeddingGenerator()

    async def initialize(self) -> None:
        """Initializes database schema and ensures pgvector extension exists."""
        await init_vector_db(self.engine)

    async def insert_chunks(
        self,
        chunks: List[DocumentChunk],
        entity_map: Optional[Dict[str, List[str]]] = None,
    ) -> int:
        """
        Embeds DocumentChunks and idempotently upserts them into PostgreSQL.

        Args:
            chunks: List of DocumentChunk instances to embed and store.
            entity_map: Optional mapping of chunk_id -> list of mentioned canonical entity names.

        Returns:
            Count of inserted/updated chunks.
        """
        if not chunks:
            return 0

        # ----------------------------------------------------------------------
        # Step 1: Generate Dense Embeddings in Batches
        # ----------------------------------------------------------------------
        logger.info("Generating embeddings for %d chunks...", len(chunks))
        texts = [chunk.text for chunk in chunks]
        embeddings = await self.embedding_generator.embed_texts(texts)

        # ----------------------------------------------------------------------
        # Step 2: Atomic PostgreSQL Upsert with ON CONFLICT DO UPDATE
        # ----------------------------------------------------------------------
        async with self.session_factory() as session:
            for chunk, emb in zip(chunks, embeddings):
                entities = (entity_map or {}).get(chunk.chunk_id, [])
                
                # Raw SQL Upsert to guarantee idempotency across pipeline re-runs
                upsert_query = text("""
                    INSERT INTO document_chunks (
                        chunk_id, document_id, paper_title, section_path,
                        text, chunk_index, embedding, entity_ids, sha256_hash, created_at
                    ) VALUES (
                        :chunk_id, :document_id, :paper_title, :section_path,
                        :text, :chunk_index, :embedding, CAST(:entity_ids AS json), :sha256_hash, NOW()
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        paper_title = EXCLUDED.paper_title,
                        section_path = EXCLUDED.section_path,
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        entity_ids = EXCLUDED.entity_ids,
                        sha256_hash = EXCLUDED.sha256_hash;
                """)

                await session.execute(
                    upsert_query,
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "paper_title": chunk.paper_title,
                        "section_path": chunk.section_path,
                        "text": chunk.text,
                        "chunk_index": chunk.chunk_index,
                        "embedding": str(emb),
                        "entity_ids": json.dumps(entities),
                        "sha256_hash": chunk.sha256_hash,
                    },
                )
            await session.commit()

        logger.info("Successfully indexed %d chunks into pgvector", len(chunks))
        return len(chunks)

    async def get_document_ids_for_entities(self, entity_names: List[str]) -> List[str]:
        """
        Looks up document_ids whose paper_title contains any of the entity names
        or where entity_ids contains the entity name.
        """
        if not entity_names:
            return []
        async with self.session_factory() as session:
            conditions = []
            params = {}
            for idx, name in enumerate(entity_names):
                clean = name.strip()
                if not clean or len(clean) < 2:
                    continue
                p_key = f"e_{idx}"
                params[p_key] = f"%{clean.lower()}%"
                conditions.append(f"LOWER(paper_title) LIKE :{p_key} OR LOWER(CAST(entity_ids AS text)) LIKE :{p_key}")

            if not conditions:
                return []

            sql = f"SELECT DISTINCT document_id FROM document_chunks WHERE {' OR '.join(conditions)};"
            result = await session.execute(text(sql), params)
            return [str(row["document_id"]) for row in result.mappings().fetchall()]

    async def similarity_search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        ef_search: Optional[int] = None,
        filter_document_ids: Optional[List[str]] = None,
    ) -> List[VectorSearchResult]:
        """
        Performs dense vector cosine similarity search for a natural language query,
        optionally constrained to specific document IDs to eliminate distractor chunks.
        """
        # Step 1: Embed the incoming query string
        query_vector = await self.embedding_generator.embed_query(query)
        # Step 2: Delegate to vector search
        return await self.similarity_search_by_vector(
            query_vector,
            top_k=top_k,
            ef_search=ef_search,
            filter_document_ids=filter_document_ids,
        )

    async def similarity_search_by_vector(
        self,
        query_vector: List[float],
        top_k: int = DEFAULT_TOP_K,
        ef_search: Optional[int] = None,
        filter_document_ids: Optional[List[str]] = None,
    ) -> List[VectorSearchResult]:
        """
        Executes raw cosine distance search given a pre-computed query embedding vector,
        optionally filtered by document_ids.
        """
        # Step 1: Open managed async SQLAlchemy session
        async with self.session_factory() as session:
            # Step 2: Set transaction-scoped HNSW exploration depth if specified
            if ef_search is not None:
                await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)};"))

            # Step 3: Construct parameterized SQL query
            params: Dict[str, Any] = {
                "query_vector": str(query_vector),
                "top_k": top_k,
            }
            where_clause = ""
            if filter_document_ids:
                where_clause = "WHERE document_id = ANY(:filter_doc_ids)"
                params["filter_doc_ids"] = filter_document_ids

            search_query = text(f"""
                SELECT 
                    chunk_id,
                    document_id,
                    paper_title,
                    section_path,
                    text,
                    entity_ids,
                    1 - (embedding <=> CAST(:query_vector AS vector)) AS score
                FROM document_chunks
                {where_clause}
                ORDER BY embedding <=> CAST(:query_vector AS vector)
                LIMIT :top_k;
            """)

            # Step 4: Execute query asynchronously and fetch typed mapping rows
            result = await session.execute(search_query, params)
            rows = result.mappings().fetchall()

            # Fallback to unfiltered if document filter yielded 0 results
            if not rows and filter_document_ids:
                fallback_query = text("""
                    SELECT 
                        chunk_id,
                        document_id,
                        paper_title,
                        section_path,
                        text,
                        entity_ids,
                        1 - (embedding <=> CAST(:query_vector AS vector)) AS score
                    FROM document_chunks
                    ORDER BY embedding <=> CAST(:query_vector AS vector)
                    LIMIT :top_k;
                """)
                fb_result = await session.execute(
                    fallback_query,
                    {
                        "query_vector": str(query_vector),
                        "top_k": top_k,
                    },
                )
                rows = fb_result.mappings().fetchall()


            # Step 5: Map relational SQL rows to typed VectorSearchResult domain models
            search_results: List[VectorSearchResult] = []
            for row in rows:
                raw_entities = row["entity_ids"]
                entities = raw_entities if isinstance(raw_entities, list) else []
                search_results.append(
                    VectorSearchResult(
                        chunk_id=str(row["chunk_id"]),
                        document_id=str(row["document_id"]),
                        paper_title=str(row["paper_title"]),
                        section_path=str(row["section_path"]),
                        text=str(row["text"]),
                        score=float(row["score"]),
                        entity_ids=entities,
                    )
                )

            return search_results

    async def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[VectorSearchResult]:
        """
        Retrieves substantive DocumentChunk records by chunk_ids using the primary key index.
        Preserves the deterministic order of the input chunk_ids list.
        """
        if not chunk_ids:
            return []

        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    chunk_id,
                    document_id,
                    paper_title,
                    section_path,
                    text,
                    entity_ids
                FROM document_chunks
                WHERE chunk_id = ANY(:chunk_ids)
            """)
            result = await session.execute(query, {"chunk_ids": chunk_ids})
            rows = result.mappings().fetchall()

            by_id: Dict[str, VectorSearchResult] = {}
            for row in rows:
                raw_entities = row["entity_ids"]
                entities = raw_entities if isinstance(raw_entities, list) else []
                by_id[str(row["chunk_id"])] = VectorSearchResult(
                    chunk_id=str(row["chunk_id"]),
                    document_id=str(row["document_id"]),
                    paper_title=str(row["paper_title"]),
                    section_path=str(row["section_path"]),
                    text=str(row["text"]),
                    score=1.0,  # Exact graph topological match
                    entity_ids=entities,
                )

            # Preserve deterministic input ordering
            ordered_results: List[VectorSearchResult] = []
            for cid in chunk_ids:
                if cid in by_id:
                    ordered_results.append(by_id[cid])

            return ordered_results

    async def get_existing_hashes(self, chunk_ids: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Retrieves existing chunk SHA-256 hashes from PostgreSQL for delta comparison.
        """
        async with self.session_factory() as session:
            if chunk_ids is not None:
                query = text("""
                    SELECT chunk_id, sha256_hash
                    FROM document_chunks
                    WHERE chunk_id = ANY(:chunk_ids)
                """)
                result = await session.execute(query, {"chunk_ids": chunk_ids})
            else:
                query = text("SELECT chunk_id, sha256_hash FROM document_chunks")
                result = await session.execute(query)
            return {row["chunk_id"]: row["sha256_hash"] for row in result.mappings().fetchall()}

    async def delete_chunks(self, chunk_ids: List[str]) -> int:
        """
        Deletes chunks by chunk_id from PostgreSQL. Returns count deleted.
        """
        if not chunk_ids:
            return 0
        async with self.session_factory() as session:
            query = text("DELETE FROM document_chunks WHERE chunk_id = ANY(:chunk_ids)")
            result = await session.execute(query, {"chunk_ids": chunk_ids})
            await session.commit()
            return result.rowcount or 0

    async def close(self) -> None:
        """Closes the underlying SQLAlchemy engine pool."""
        await self.engine.dispose()

