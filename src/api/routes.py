"""
FastAPI HTTP Route Definitions.

Architecture Role:
    Part of Phase 7 (FastAPI Application Service). Exposes REST API endpoints for user querying,
    system health diagnostics, and runtime statistics. Coordinates the retrieval coordinator and
    answer synthesizer pipelines.

Inputs:
    - HTTP requests with validated payloads (`QueryRequest`).

Outputs:
    - JSON responses (`QueryResponse`, `HealthResponse`, `StatsResponse`).

Design Decisions:
    - Clean Dependency Injection: Uses FastAPI dependencies (`Depends`) with singletons, allowing
      trivial override in automated integration tests.
    - Non-Blocking Health Probes: Inspects database connectivity asynchronously using timeouts
      so a single offline backend does not hang health checks indefinitely.
"""

from functools import lru_cache
import time
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text

from src.api.schemas import (
    ChunkDetailResponse,
    CommunityDetectionResponse,
    HealthResponse,
    IncrementalIngestRequest,
    IncrementalIngestResponse,
    IngestRequest,
    IngestStatusResponse,
    QueryRequest,
    QueryResponse,
    StatsResponse,
    SubgraphResponse,
)
from src.core.cache import QueryResponseCache
from src.core.config import get_settings
from src.core.logging import setup_logger
from src.ingestion.orchestrator import IngestionOrchestrator, get_ingestion_orchestrator
from src.router.coordinator import RetrievalCoordinator
from src.synthesis.synthesizer import AnswerSynthesizer, SynthesizedAnswer
from src.vector.schema import DocumentChunkModel

import uuid

logger = setup_logger(name="api.routes")
router = APIRouter(tags=["Enterprise GraphRAG"])
SERVER_BOOT_ID: str = str(uuid.uuid4())

# ==============================================================================
# Dependency Singletons & Providers
# ==============================================================================
@lru_cache()
def get_shared_cache() -> QueryResponseCache:
    """Provides a shared singleton instance of the query response cache."""
    return QueryResponseCache()


@lru_cache()
def get_coordinator() -> RetrievalCoordinator:
    """Provides a shared singleton instance of the RetrievalCoordinator."""
    return RetrievalCoordinator()


@lru_cache()
def get_synthesizer() -> AnswerSynthesizer:
    """Provides a shared singleton instance of the AnswerSynthesizer."""
    return AnswerSynthesizer(cache=get_shared_cache())


# ==============================================================================
# API Endpoints
# ==============================================================================
@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute grounded GraphRAG query",
    description=(
        "Processes a natural language query through multi-turn session resolution, "
        "intent classification (graph vs vector vs both), multi-modal retrieval, "
        "and strict citation-grounded synthesis."
    ),
)
async def query_endpoint(
    payload: QueryRequest,
    request: Request,
    coordinator: RetrievalCoordinator = Depends(get_coordinator),
    synthesizer: AnswerSynthesizer = Depends(get_synthesizer),
) -> QueryResponse:
    """
    Handles end-to-end question answering across Neo4j and pgvector.
    """
    req_start = time.time()
    logger.info("Received query request: '%s' (session='%s')", payload.query, payload.session_id)

    try:
        # Step 1: Execute retrieval coordination (session coreference + router + db searches)
        forced_route = None
        requested_eval_mode = request.headers.get("X-GraphRAG-Eval-Mode", "").strip().lower()
        if requested_eval_mode and get_settings().enable_eval_mode_override:
            if requested_eval_mode == "vector":
                from src.router.models import RouteDecision
                forced_route = RouteDecision.VECTOR
            elif requested_eval_mode in {"hybrid", "both"}:
                from src.router.models import RouteDecision
                forced_route = RouteDecision.BOTH
            else:
                raise HTTPException(status_code=400, detail="Unsupported evaluation mode; use vector or hybrid")

        retrieval_ctx = await coordinator.retrieve(
            query=payload.query,
            session_id=payload.session_id,
            top_k=payload.top_k,
            forced_route=forced_route,
        )

        # Step 2: Synthesize grounded response and validate citations
        synthesized: SynthesizedAnswer = await synthesizer.synthesize(
            context=retrieval_ctx,
            use_cache=payload.use_cache,
        )

        # Step 3: Consolidate latency metrics across retrieval and synthesis phases
        total_latencies: Dict[str, float] = {}
        total_latencies.update(retrieval_ctx.latency_ms)
        total_latencies.update(synthesized.latency_ms)
        total_latencies["total_request_ms"] = round((time.time() - req_start) * 1000.0, 2)

        # Step 4: Extract traversed subgraph for inline UI visualization
        subgraph_response = None
        if retrieval_ctx.subgraph and retrieval_ctx.subgraph.get("nodes"):
            try:
                subgraph_response = SubgraphResponse(**retrieval_ctx.subgraph)
            except Exception as sub_err:
                logger.warning("Failed to serialize response subgraph: %s", sub_err)

        # Step 5: Assemble and return structured response
        chunk_texts = [
            f"[{c.chunk_id}] {c.text}" if not c.text.startswith(f"[{c.chunk_id}]") else c.text
            for c in (retrieval_ctx.retrieved_chunks or [])
        ]
        return QueryResponse(
            query=synthesized.query,
            answer=synthesized.answer,
            route_taken=synthesized.route,
            citations=synthesized.cited_chunk_ids,
            is_grounded=synthesized.validation_result.is_valid,
            from_cache=synthesized.from_cache,
            graph_facts=retrieval_ctx.graph_facts,
            retrieved_chunks=chunk_texts,
            latency_breakdown_ms=total_latencies,
            subgraph=subgraph_response,
        )


    except Exception as exc:
        logger.error("Unhandled error during query processing: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(exc)}",
        ) from exc


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Probe database and system health",
    description="Asynchronously tests connectivity to Neo4j and PostgreSQL databases.",
)
async def health_endpoint(
    coordinator: RetrievalCoordinator = Depends(get_coordinator),
) -> HealthResponse:
    """
    Checks active connections to Neo4j and PostgreSQL backends.
    """
    neo4j_ok = False
    postgres_ok = False

    # Step 1: Probe Neo4j connectivity
    try:
        driver = await coordinator.query_engine.writer.get_driver()
        await driver.verify_connectivity()
        neo4j_ok = True
    except Exception as exc:
        logger.warning("Health probe: Neo4j is offline or unreachable (%s)", exc)

    # Step 2: Probe PostgreSQL / pgvector connectivity
    try:
        async with coordinator.vector_store.engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        postgres_ok = True
    except Exception as exc:
        logger.warning("Health probe: PostgreSQL is offline or unreachable (%s)", exc)

    # Step 3: Determine aggregate system status
    system_status = "healthy" if (neo4j_ok and postgres_ok) else "degraded"

    return HealthResponse(
        status=system_status,
        neo4j_connected=neo4j_ok,
        postgres_connected=postgres_ok,
        boot_id=SERVER_BOOT_ID,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve cache performance statistics",
    description="Returns cache hit rate, total query count, and memory entry count.",
)
async def stats_endpoint(
    cache: QueryResponseCache = Depends(get_shared_cache),
) -> StatsResponse:
    """
    Returns query cache efficiency diagnostics.
    """
    stats = cache.stats
    settings = get_settings()
    return StatsResponse(
        total_requests=stats.total_requests,
        cache_hits=stats.hits,
        cache_misses=stats.misses,
        cache_hit_rate=round(stats.hit_rate, 4),
        cached_entries=cache.size(),
        acknowledgments=settings.arxiv_acknowledgment,
        models={
            "extraction_model": settings.extraction_model,
            "router_model": settings.router_model,
            "synthesis_model": settings.synthesis_model,
            "embedding_model": settings.embedding_model,
            "embedding_dim": settings.embedding_dimension,
            "llm_base_url": settings.llm_base_url,
        },
        infrastructure={
            "neo4j_uri": settings.neo4j_uri,
            "postgres_target": f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
            "cache_backend": "in_memory_lru",
        },
    )


@router.get(
    "/graph/subgraph",
    response_model=SubgraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Neo4j graph topology for UI visualization",
    description="Returns ontology nodes and directed relationship edges formatted for force-directed canvas rendering.",
)
async def subgraph_endpoint(
    limit: int = 100,
    entity_type: Optional[str] = None,
    coordinator: RetrievalCoordinator = Depends(get_coordinator),
) -> SubgraphResponse:
    """
    Supplies subgraph topology data to the Material 3 graph explorer.
    """
    try:
        data = await coordinator.query_engine.get_subgraph(
            limit=limit,
            entity_type=entity_type,
        )
        return SubgraphResponse(**data)
    except Exception as exc:
        logger.error("Failed to query Neo4j subgraph: %s", exc)
        return SubgraphResponse(nodes=[], edges=[], total_nodes=0, total_edges=0)


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch raw chunk passage backing a grounded citation",
    description="Returns raw text, section path, and document metadata for citation popover inspection.",
)
async def chunk_detail_endpoint(
    chunk_id: str,
    coordinator: RetrievalCoordinator = Depends(get_coordinator),
) -> ChunkDetailResponse:
    """
    Returns full text and metadata for a specific document chunk.
    """
    try:
        async with coordinator.vector_store.session_factory() as session:
            row = await session.get(DocumentChunkModel, chunk_id)
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chunk '{chunk_id}' not found in database",
                )
            return ChunkDetailResponse(
                chunk_id=str(row.chunk_id),
                document_id=str(row.document_id),
                paper_title=str(row.paper_title),
                section_path=str(row.section_path),
                text=str(row.text),
                entity_ids=list(row.entity_ids) if row.entity_ids else [],
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving chunk detail for %s: %s", chunk_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database lookup failed: {str(exc)}",
        ) from exc


@router.post(
    "/ingest",
    response_model=IngestStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger asynchronous corpus ingestion",
    description="Initiates background harvesting, chunking, pgvector indexing, and/or Neo4j knowledge graph population.",
)
async def ingest_endpoint(
    request: IngestRequest,
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> IngestStatusResponse:
    """
    Kicks off an asynchronous corpus ingestion pipeline job.
    """
    started = await orchestrator.start_ingestion(request)
    if not started:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingestion job is already currently running. Please wait for it to complete.",
        )
    return orchestrator.get_status()


@router.get(
    "/ingest/status",
    response_model=IngestStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll status and progress of corpus ingestion",
    description="Returns active progress percentage, current stage, items processed, and recent logs.",
)
async def ingest_status_endpoint(
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> IngestStatusResponse:
    """
    Polls the active state and progress of the background ingestion engine.
    """
    return orchestrator.get_status()


@router.get(
    "/graph/communities",
    response_model=CommunityDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect research communities and corpus-level summaries",
    description="Executes Label Propagation Algorithm (LPA) clustering over the Neo4j graph and returns hierarchical community summaries.",
)
async def communities_endpoint(
    force_refresh: bool = False,
) -> CommunityDetectionResponse:
    """
    Discovers topological communities and synthesizes corpus-level thematic summaries.
    """
    try:
        from src.graph.community import get_community_detector

        detector = get_community_detector()
        records = await detector.detect_communities(force_refresh=force_refresh)
        return CommunityDetectionResponse(
            total_communities=len(records),
            communities=records,
        )
    except Exception as exc:
        logger.error("Failed to detect graph communities: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Community detection failed: {str(exc)}",
        ) from exc


@router.post(
    "/ingest/paper",
    response_model=IncrementalIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Incrementally ingest a single publication",
    description="Chunks, embeds in pgvector, and extracts/merges facts into Neo4j for a single paper without full corpus rescanning.",
)
async def ingest_paper_endpoint(
    payload: IncrementalIngestRequest,
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> IncrementalIngestResponse:
    """
    Incrementally ingests a single paper document into pgvector and Neo4j.
    """
    try:
        from src.ingestion.models import Author, Paper

        author_objects = [Author(name=a) for a in payload.authors]
        paper = Paper(
            paper_id=payload.paper_id,
            title=payload.title,
            abstract=payload.abstract,
            authors=author_objects,
            published_year=payload.published_year,
            venue=payload.venue,
            full_text=payload.full_text or payload.abstract,
        )

        result = await orchestrator.ingest_paper_incremental(
            paper=paper,
            populate_pgvector=payload.populate_pgvector,
            populate_neo4j=payload.populate_neo4j,
        )

        return IncrementalIngestResponse(
            paper_id=result["paper_id"],
            title=result["title"],
            chunks_created=result["chunks_created"],
            facts_written=result["facts_written"],
            entities_written=result["entities_written"],
            vectors_upserted=result["vectors_upserted"],
            status=result["status"],
        )
    except Exception as exc:
        logger.error("Incremental paper ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incremental ingestion failed: {str(exc)}",
        ) from exc


