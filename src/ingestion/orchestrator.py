"""
Ingestion Orchestration Engine.

Role in Architecture:
    Coordinates asynchronous end-to-end corpus acquisition, boundary chunking,
    dense vector embedding (pgvector), and LLM fact extraction and knowledge graph
    persistence (Neo4j). Exposes thread-safe state tracking for frontend progress telemetry.

Inputs:
    IngestRequest configuration (harvest query, paper limit, chunk cap, pipeline toggles).

Outputs:
    Populated vector database and Neo4j knowledge graph, accompanied by atomic
    progress updates polled via GET /ingest/status.
"""

import asyncio
from collections import deque
import json
import os
from typing import List, Optional

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.ingestion.models import DocumentChunk, IngestRequest, IngestStatusResponse, Paper

logger = setup_logger("ingestion.orchestrator")


CHECKPOINT_FILE = "data/corpus/ingestion_checkpoint.json"


class IngestionOrchestrator:
    """
    Manages the lifecycle of asynchronous corpus ingestion tasks.
    Maintains an atomic in-memory status record queried by the UI progress bar.
    Equipped with persistent checkpointing to resume interrupted runs seamlessly.
    """

    def __init__(self) -> None:
        self.status: str = "idle"
        self.stage: str = "idle"
        self.progress_pct: float = 0.0
        self.current_item: int = 0
        self.total_items: int = 0
        self.message: str = "Ingestion engine idle and ready."
        self._logs: deque = deque(maxlen=60)
        self._is_running: bool = False
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    @staticmethod
    def _load_checkpoint() -> set[str]:
        """Loads completed chunk IDs from disk checkpoint."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.get("completed_chunk_ids", []))
            except Exception as exc:
                logger.warning("Could not read checkpoint file: %s", exc)
        return set()

    @staticmethod
    def _save_checkpoint(completed_chunk_ids: set[str], total_facts: int) -> None:
        """Persists completed chunk IDs to disk checkpoint."""
        try:
            os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "completed_chunk_ids": sorted(list(completed_chunk_ids)),
                        "total_facts_written": total_facts,
                    },
                    f,
                    indent=2,
                )
        except Exception as exc:
            logger.warning("Could not write checkpoint file: %s", exc)

    @staticmethod
    def _clear_checkpoint() -> None:
        """Removes the checkpoint file to allow a fresh run."""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                os.remove(CHECKPOINT_FILE)
            except Exception:
                pass

    def _log(self, text: str) -> None:
        """Appends a timestamped line to the circular log queue."""
        logger.info("[Ingest] %s", text)
        self._logs.append(text)

    def get_status(self) -> IngestStatusResponse:
        """Returns the current snapshot of the ingestion pipeline state."""
        return IngestStatusResponse(
            status=self.status,
            stage=self.stage,
            progress_pct=round(self.progress_pct, 1),
            current_item=self.current_item,
            total_items=self.total_items,
            message=self.message,
            logs=list(self._logs),
        )

    async def start_ingestion(self, request: IngestRequest) -> bool:
        """
        Initiates the asynchronous ingestion pipeline if not already running.

        Args:
            request: Configuration parameters for the run.

        Returns:
            True if execution successfully initiated, False if already in progress.
        """
        async with self._lock:
            if self._is_running:
                return False

            self._is_running = True
            self.status = "running"
            self.stage = "initializing"
            self.progress_pct = 0.0
            self.current_item = 0
            self.total_items = 0
            self.message = "Initializing ingestion pipeline..."
            self._logs.clear()
            self._log(f"Starting ingestion job (mode='{request.mode}', neo4j={request.populate_neo4j}, pgvector={request.populate_pgvector})")

            # Spawn asynchronous worker task
            self._task = asyncio.create_task(self._run_pipeline(request))
            return True

    async def _run_pipeline(self, request: IngestRequest) -> None:
        """
        Internal worker executing the sequential ingestion stages.
        """
        try:
            chunks: List[DocumentChunk] = []

            # ------------------------------------------------------------------
            # Stage 1: Acquisition (if harvest_arxiv selected)
            # ------------------------------------------------------------------
            if request.mode == "harvest_arxiv":
                from src.ingestion.collector import PaperCollector
                from src.ingestion.chunker import DocumentChunker

                self.stage = "harvesting"
                self.message = f"Querying arXiv for '{request.query}' (limit={request.paper_limit})..."
                self.progress_pct = 5.0
                self._log(f"Stage: Harvesting papers from arXiv (query='{request.query}', limit={request.paper_limit})")

                collector = PaperCollector()
                papers = await collector.collect(query=request.query, limit=request.paper_limit)
                self._log(f"Harvested {len(papers)} papers from arXiv.")

                # Ensure storage directory exists
                os.makedirs("data/corpus", exist_ok=True)
                with open("data/corpus/papers.json", "w", encoding="utf-8") as f:
                    json.dump([p.model_dump() for p in papers], f, indent=2, default=str)

                # Stage 1b: Natural boundary chunking
                self.stage = "chunking"
                self.message = f"Chunking {len(papers)} harvested papers..."
                self.progress_pct = 15.0
                self._log("Stage: Chunking documents into boundary-aligned passages")

                chunker = DocumentChunker()
                for paper in papers:
                    paper_chunks = chunker.chunk_paper(paper)
                    chunks.extend(paper_chunks)

                with open("data/corpus/chunks.json", "w", encoding="utf-8") as f:
                    json.dump([c.model_dump() for c in chunks], f, indent=2)
                self._log(f"Created {len(chunks)} total text chunks.")

            else:
                # Load existing corpus from disk
                self.stage = "loading_corpus"
                self.message = "Loading pre-existing corpus from data/corpus/chunks.json..."
                self.progress_pct = 10.0
                self._log("Loading existing corpus from disk...")

                corpus_path = "data/corpus/chunks.json"
                if not os.path.exists(corpus_path):
                    raise FileNotFoundError(f"Corpus file '{corpus_path}' not found. Please select 'harvest_arxiv' mode.")

                with open(corpus_path, "r", encoding="utf-8") as f:
                    raw_chunks = json.load(f)
                    chunks = [DocumentChunk(**c) for c in raw_chunks]
                self._log(f"Loaded {len(chunks)} pre-existing chunks.")

            # Apply chunk limit if specified by user
            if request.chunk_limit and request.chunk_limit < len(chunks):
                chunks = chunks[:request.chunk_limit]
                self._log(f"Constrained corpus to first {len(chunks)} chunks per chunk_limit parameter.")

            if not chunks:
                raise ValueError("No document chunks available to process.")

            # ------------------------------------------------------------------
            # Incremental Hash-Based Delta Detection
            # ------------------------------------------------------------------
            chunks_to_process = chunks
            if request.incremental and not request.reset_checkpoint:
                from src.vector.indexer import VectorStore
                probe_store = VectorStore()
                try:
                    await probe_store.initialize()
                    existing_hashes = await probe_store.get_existing_hashes([c.chunk_id for c in chunks])
                    
                    stale_ids: List[str] = []
                    unchanged_ids: List[str] = []
                    delta_list: List[DocumentChunk] = []

                    for c in chunks:
                        if c.chunk_id in existing_hashes:
                            if existing_hashes[c.chunk_id] == c.sha256_hash:
                                unchanged_ids.append(c.chunk_id)
                            else:
                                stale_ids.append(c.chunk_id)
                                delta_list.append(c)
                        else:
                            delta_list.append(c)

                    if stale_ids:
                        self._log(f"Incremental update: purging {len(stale_ids)} modified/stale chunks from pgvector and Neo4j...")
                        await probe_store.delete_chunks(stale_ids)
                        if request.populate_neo4j:
                            from src.graph.writer import Neo4jWriter
                            p_writer = Neo4jWriter()
                            await p_writer.delete_edges_for_chunks(stale_ids)
                            await p_writer.close()

                    self._log(f"Incremental analysis: {len(unchanged_ids)} unchanged chunks skipped, {len(delta_list)} delta chunks to process.")
                    chunks_to_process = delta_list
                except Exception as delta_err:
                    logger.warning("Incremental delta probe failed, falling back to full processing: %s", delta_err)
                    chunks_to_process = chunks
                finally:
                    await probe_store.close()

                if not chunks_to_process:
                    self.stage = "completed"
                    self.status = "completed"
                    self.progress_pct = 100.0
                    self.message = f"Incremental update complete: all {len(chunks)} chunks are already up-to-date."
                    self._log(self.message)
                    return

            # ------------------------------------------------------------------
            # Stage 2: Dense Vector Indexing (pgvector)
            # ------------------------------------------------------------------
            if request.populate_pgvector and chunks_to_process:
                from src.vector.indexer import VectorStore

                self.stage = "embedding"
                self.message = f"Indexing {len(chunks_to_process)} delta chunks into PostgreSQL pgvector..."
                self.progress_pct = 25.0
                self.current_item = 0
                self.total_items = len(chunks_to_process)
                self._log(f"Stage: Inserting {len(chunks_to_process)} delta chunks into pgvector...")

                store = VectorStore()
                await store.initialize()
                inserted_count = await store.insert_chunks(chunks_to_process)
                self._log(f"Successfully inserted/updated {inserted_count} vector chunks.")
                self.progress_pct = 40.0

            # ------------------------------------------------------------------
            # Stage 3: Knowledge Graph Extraction & Writing (Neo4j)
            # ------------------------------------------------------------------
            if request.populate_neo4j and chunks_to_process:
                from src.graph.extractor import GraphExtractor
                from src.graph.resolver import EntityResolver
                from src.graph.writer import Neo4jWriter

                self.stage = "extracting"
                self.message = f"Extracting facts from {len(chunks_to_process)} chunks via LLM..."
                self.total_items = len(chunks_to_process)
                self._log(f"Stage: Extracting ontology facts from {len(chunks_to_process)} chunks...")

                # Load existing checkpoint or reset if requested
                if request.reset_checkpoint:
                    self._clear_checkpoint()
                    completed_chunk_ids: set[str] = set()
                    self._log("Cleared existing checkpoint per reset_checkpoint=True.")
                else:
                    completed_chunk_ids = self._load_checkpoint()
                    if completed_chunk_ids:
                        self._log(f"Resuming from checkpoint: {len(completed_chunk_ids)} chunks already completed.")

                extractor = GraphExtractor()
                resolver = EntityResolver()
                writer = Neo4jWriter()
                await writer.init_schema()

                base_pct = 40.0 if request.populate_pgvector else 15.0
                span_pct = 100.0 - base_pct - 5.0  # Reserve last 5% for completion
                total_facts_written = 0

                try:
                    for i, chunk in enumerate(chunks_to_process):
                        self.current_item = i + 1
                        self.progress_pct = base_pct + (span_pct * ((i + 1) / len(chunks_to_process)))

                        # Checkpoint guard: skip already written chunks
                        if chunk.chunk_id in completed_chunk_ids and not request.reset_checkpoint:
                            self.message = f"Skipped (checkpointed): chunk {i + 1}/{len(chunks_to_process)} ({chunk.chunk_id})"
                            continue

                        self.message = f"Extracting facts: chunk {i + 1}/{len(chunks_to_process)} ({chunk.chunk_id})"

                        # Step-by-step extraction per chunk with caching
                        facts = await extractor.extract_chunk(chunk)
                        if facts:
                            # Resolve entities & write to Neo4j
                            resolved_entities, resolved_facts = await resolver.resolve_and_link(facts)
                            if resolved_entities:
                                await writer.write_entities(resolved_entities)
                            if resolved_facts:
                                await writer.write_facts(resolved_facts)
                            total_facts_written += len(resolved_facts)
                            self._log(f"Chunk {i + 1}/{len(chunks_to_process)}: Wrote {len(resolved_facts)} facts ({len(resolved_entities)} entities) to Neo4j.")
                        else:
                            self._log(f"Chunk {i + 1}/{len(chunks_to_process)}: 0 facts extracted (cached or empty).")

                        # Commit chunk to persistent checkpoint immediately
                        completed_chunk_ids.add(chunk.chunk_id)
                        self._save_checkpoint(completed_chunk_ids, total_facts_written)

                        # Yield control to event loop
                        await asyncio.sleep(0.01)

                    # Step 4: Refresh in-memory entity registry in query engine
                    from src.graph.query_engine import GraphQueryEngine
                    engine = GraphQueryEngine(writer=writer, resolver=resolver)
                    await engine.sync_registry_from_graph()

                finally:
                    await writer.close()

            # ------------------------------------------------------------------
            # Finalization
            # ------------------------------------------------------------------
            self.stage = "completed"
            self.status = "completed"
            self.progress_pct = 100.0
            self.message = f"Ingestion completed successfully! Processed {len(chunks)} chunks."
            self._log(self.message)

        except Exception as exc:
            logger.exception("Ingestion pipeline failed: %s", exc)
            self.stage = "failed"
            self.status = "failed"
            self.message = f"Ingestion failed: {str(exc)}"
            self._log(f"ERROR: {str(exc)}")

        finally:
            self._is_running = False

    async def ingest_paper_incremental(
        self,
        paper: Paper,
        populate_pgvector: bool = True,
        populate_neo4j: bool = True,
    ) -> dict:
        """
        Incrementally processes and ingests a single publication into pgvector and Neo4j without full corpus rebuild.

        Steps:
            1. Slices paper into DocumentChunks via DocumentChunker.
            2. Upserts chunks into PostgreSQL pgvector (ON CONFLICT DO UPDATE).
            3. Extracts ontology facts via GraphExtractor (leveraging SHA-256 caching).
            4. Writes nodes and relationships into Neo4j via idempotent MERGE.
            5. Synchronizes the in-memory EntityResolver registry in GraphQueryEngine.
            6. Updates persistent checkpoint and local chunks store.

        Returns:
            Dictionary summarizing paper_id, chunks_created, facts_written, and entities_written.
        """
        from src.ingestion.chunker import DocumentChunker

        logger.info("Starting incremental ingestion for paper '%s' (ID: %s)...", paper.title, paper.paper_id)

        # 1. Chunking
        chunker = DocumentChunker()
        chunks = chunker.chunk_paper(paper)
        if not chunks:
            logger.warning("Paper '%s' yielded 0 chunks (insufficient text).", paper.paper_id)
            return {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "chunks_created": 0,
                "facts_written": 0,
                "entities_written": 0,
                "status": "empty_chunks",
            }

        # 2. Vector indexing
        inserted_vectors = 0
        if populate_pgvector:
            from src.vector.indexer import VectorStore

            store = VectorStore()
            await store.initialize()
            inserted_vectors = await store.insert_chunks(chunks)
            logger.info("Incremental pgvector: upserted %d vector records.", inserted_vectors)

        # 3. Knowledge Graph extraction & writing
        total_facts = 0
        total_entities = 0
        if populate_neo4j:
            from src.graph.extractor import GraphExtractor
            from src.graph.resolver import EntityResolver
            from src.graph.writer import Neo4jWriter

            extractor = GraphExtractor()
            resolver = EntityResolver()
            writer = Neo4jWriter()
            await writer.init_schema()

            completed_checkpoint = self._load_checkpoint()

            try:
                for chunk in chunks:
                    extracted = await extractor.extract_chunk(chunk)
                    if extracted:
                        resolved_entities, resolved_facts = await resolver.resolve_and_link(extracted)
                        if resolved_entities:
                            await writer.write_entities(resolved_entities)
                            total_entities += len(resolved_entities)
                        if resolved_facts:
                            await writer.write_facts(resolved_facts)
                            total_facts += len(resolved_facts)

                    completed_checkpoint.add(chunk.chunk_id)

                self._save_checkpoint(completed_checkpoint, total_facts)
                logger.info(
                    "Incremental Neo4j: wrote %d facts across %d entities for paper '%s'.",
                    total_facts,
                    total_entities,
                    paper.paper_id,
                )

                # Sync in-memory entity registry in query engine
                from src.graph.query_engine import GraphQueryEngine

                engine = GraphQueryEngine(writer=writer, resolver=resolver)
                await engine.sync_registry_from_graph()

            finally:
                await writer.close()

        # 4. Append to local chunks file if exists
        corpus_path = "data/corpus/chunks.json"
        if os.path.exists(corpus_path):
            try:
                with open(corpus_path, "r", encoding="utf-8") as f:
                    existing_raw = json.load(f)
                existing_ids = {c["chunk_id"] for c in existing_raw}
                new_chunk_dicts = [c.model_dump() for c in chunks if c.chunk_id not in existing_ids]
                if new_chunk_dicts:
                    existing_raw.extend(new_chunk_dicts)
                    with open(corpus_path, "w", encoding="utf-8") as f:
                        json.dump(existing_raw, f, indent=2)
            except Exception as exc:
                logger.warning("Could not append incremental chunks to %s: %s", corpus_path, exc)

        return {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "chunks_created": len(chunks),
            "facts_written": total_facts,
            "entities_written": total_entities,
            "vectors_upserted": inserted_vectors,
            "status": "success",
        }


# Module-level singleton
_orchestrator: Optional[IngestionOrchestrator] = None


def get_ingestion_orchestrator() -> IngestionOrchestrator:
    """Returns the singleton instance of the IngestionOrchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IngestionOrchestrator()
    return _orchestrator
