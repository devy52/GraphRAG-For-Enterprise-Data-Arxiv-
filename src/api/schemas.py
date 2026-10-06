"""
FastAPI Request and Response Data Schemas.

Architecture Role:
    Part of Phase 7 (FastAPI Application Service). Defines Pydantic request models, response DTOs,
    and status schemas for public HTTP endpoints (`/query`, `/health`, `/stats`).

Inputs:
    - Inbound JSON payloads for user queries.
    - System health check probe requests.

Outputs:
    - Strongly-typed JSON response structures containing grounded answers, verified citations,
      retrieval routes, and latency profiles.

Design Decisions:
    - Strict Input Validation: Rejects empty or oversized queries (>1000 chars) at the API boundary.
    - Transparent Traceability: Returns `route_taken`, `latency_breakdown_ms`, and `citations` in
      every `/query` response for enterprise auditability and monitoring.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.router.models import RouteDecision


class QueryRequest(BaseModel):
    """
    Inbound query payload for the enterprise GraphRAG search endpoint.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language question to answer against the research corpus",
        examples=["What methods extend Dense Passage Retrieval and what are their benchmark scores?"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for conversational memory and multi-turn pronoun resolution",
        examples=["session_user_42"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of dense vector chunks to retrieve during vector or hybrid routes",
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to serve or store responses in the normalized query response cache",
    )


class GraphNode(BaseModel):
    """Represents a node in the Neo4j knowledge graph topology for UI visualization."""
    id: str = Field(..., description="Unique node identifier or canonical name")
    label: str = Field(..., description="Display label for the node")
    type: str = Field(..., description="Ontology entity type (Paper, Method, Dataset, Author, Topic, etc.)")
    aliases: List[str] = Field(default_factory=list, description="Resolved alternative surface forms")


class GraphEdge(BaseModel):
    """Represents a directed relationship edge between two ontology entities."""
    source: str = Field(..., description="Source entity name/id")
    target: str = Field(..., description="Target entity name/id")
    type: str = Field(..., description="Relationship predicate type (e.g. EXTENDS, USES_DATASET)")
    source_chunk_id: Optional[str] = Field(None, description="Grounding source chunk ID")
    confidence: float = Field(default=1.0, description="Extraction confidence score")


class SubgraphResponse(BaseModel):
    """Graph topology snapshot payload returned for UI visualization."""
    nodes: List[GraphNode] = Field(default_factory=list, description="List of graph nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="List of graph edges")
    total_nodes: int = Field(..., description="Total node count")
    total_edges: int = Field(..., description="Total relationship edge count")


class QueryResponse(BaseModel):
    """
    Outbound response containing the grounded answer, verified citations, and execution metadata.
    """
    query: str = Field(..., description="Processed user query")
    answer: str = Field(..., description="Synthesized, citation-grounded response text")
    route_taken: RouteDecision = Field(
        ...,
        description="Retrieval path selected by the classifier: 'graph', 'vector', or 'both'",
    )
    citations: List[str] = Field(
        default_factory=list,
        description="List of verified chunk IDs cited in the answer",
    )
    is_grounded: bool = Field(
        ...,
        description="True if the answer passed strict deterministic citation validation",
    )
    from_cache: bool = Field(
        default=False,
        description="True if the answer was served directly from QueryResponseCache",
    )
    graph_facts: List[str] = Field(
        default_factory=list,
        description="Declarative statements retrieved from the Neo4j knowledge graph",
    )
    retrieved_chunks: List[str] = Field(
        default_factory=list,
        description="Passage texts retrieved from pgvector for grounded evaluation and transparency",
    )
    latency_breakdown_ms: Dict[str, float] = Field(
        default_factory=dict,
        description="Execution latencies for routing, retrieval, synthesis, and validation in milliseconds",
    )
    subgraph: Optional[SubgraphResponse] = Field(
        default=None,
        description="Traversed subgraph nodes and edges for inline UI visualization",
    )


class HealthResponse(BaseModel):
    """
    System health probe status across database backends and cache tiers.
    """
    status: str = Field(..., description="'healthy' or 'degraded'")
    neo4j_connected: bool = Field(..., description="True if Neo4j graph database responded to ping")
    postgres_connected: bool = Field(..., description="True if PostgreSQL / pgvector database responded to ping")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the health check inspection",
    )
    boot_id: str = Field(
        default="",
        description="Unique process boot identifier to detect server restarts",
    )


class StatsResponse(BaseModel):
    """
    Diagnostic runtime metrics for cache hit rate and query throughput.
    """
    total_requests: int = Field(..., description="Total query requests handled by the cache tier")
    cache_hits: int = Field(..., description="Total cache hits")
    cache_misses: int = Field(..., description="Total cache misses")
    cache_hit_rate: float = Field(..., description="Proportion of queries served from cache (0.0 to 1.0)")
    cached_entries: int = Field(..., description="Number of queries currently stored in the cache")
    acknowledgments: str = Field(
        default="Thank you to arXiv for use of its open access interoperability.",
        description="Open access data attribution notice",
    )
    models: Dict[str, Any] = Field(
        default_factory=dict,
        description="Active model configurations dynamically loaded from environment settings",
    )
    infrastructure: Dict[str, Any] = Field(
        default_factory=dict,
        description="Active database and cache infrastructure connection targets",
    )


class ChunkDetailResponse(BaseModel):
    """Detail payload for inspecting raw chunk text backing a grounded citation."""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document/paper identifier")
    paper_title: str = Field(..., description="Publication title")
    section_path: str = Field(..., description="Document section path")
    text: str = Field(..., description="Raw chunk text passage")
    entity_ids: List[str] = Field(default_factory=list, description="Referenced canonical entities")


from src.graph.community import CommunityDetectionResponse, CommunitySummaryRecord


class IncrementalIngestRequest(BaseModel):
    """Payload for incrementally ingesting a single paper."""
    paper_id: str = Field(..., description="Unique paper identifier, e.g. arXiv ID or internal doc ID")
    title: str = Field(..., description="Title of the paper")
    abstract: str = Field(default="", description="Abstract of the paper")
    authors: List[str] = Field(default_factory=list, description="Author names")
    published_year: Optional[int] = Field(default=None, description="Publication year")
    venue: Optional[str] = Field(default=None, description="Venue or conference")
    full_text: Optional[str] = Field(default=None, description="Body text or full text")
    populate_pgvector: bool = Field(default=True, description="Upsert into pgvector")
    populate_neo4j: bool = Field(default=True, description="Extract and merge into Neo4j")


class IncrementalIngestResponse(BaseModel):
    """Outcome payload for incremental paper ingestion."""
    paper_id: str
    title: str
    chunks_created: int
    facts_written: int
    entities_written: int
    vectors_upserted: int
    status: str


from src.ingestion.models import IngestRequest, IngestStatusResponse

__all__ = [
    "QueryRequest",
    "QueryResponse",
    "HealthResponse",
    "StatsResponse",
    "GraphNode",
    "GraphEdge",
    "SubgraphResponse",
    "ChunkDetailResponse",
    "CommunitySummaryRecord",
    "CommunityDetectionResponse",
    "IncrementalIngestRequest",
    "IncrementalIngestResponse",
    "IngestRequest",
    "IngestStatusResponse",
]


