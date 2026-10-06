"""
Question Router Data Models & Enums.

Architecture Role:
    Part of Phase 5 (Question Router & Session Memory). Defines the structural representations
    and contracts for query routing decisions, intent confidence scores, and multi-modal
    retrieval contexts combining knowledge graph facts and dense vector chunks.

Inputs:
    - User query strings and resolved coreference terms.
    - Graph facts extracted from Neo4j query templates.
    - Dense vector search results from pgvector.

Outputs:
    - Structured `RouteDecision` classifications (GRAPH, VECTOR, BOTH).
    - `RoutingResult` tracking the decision rationale, confidence, and target Cypher template.
    - Unified `RetrievalContext` feeding the Phase 6 synthesis and citation validation engine.

Design Decisions:
    - Tri-State Routing: 'graph' for relational/topological queries, 'vector' for semantic/content
      queries, and 'both' (hybrid) for multifaceted questions or low-confidence escalations.
    - Explicit Latency & Citation Accounting: `RetrievalContext` tracks sub-operation latencies
      and aggregates all potential `cited_chunk_ids` for strict provenance validation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.vector.models import VectorSearchResult


class RouteDecision(str, Enum):
    """
    Available routing paths for an incoming query.
    """
    GRAPH = "graph"    # Knowledge graph traversal (relational, multi-hop, lineage)
    VECTOR = "vector"  # Dense vector similarity search (unstructured text, semantic explanations)
    BOTH = "both"      # Hybrid retrieval (combines graph facts + vector text chunks)


class RoutingResult(BaseModel):
    """
    Captures the decision output of the RouteClassifier.
    """
    decision: RouteDecision = Field(
        ...,
        description="The chosen retrieval route: 'graph', 'vector', or 'both'",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification decision (0.0 to 1.0)",
    )
    reasoning: str = Field(
        ...,
        description="Explanation or heuristic basis for the routing choice",
    )
    resolved_query: str = Field(
        ...,
        description="The query string after session coreference resolution",
    )
    detected_entities: List[str] = Field(
        default_factory=list,
        description="Canonical entities identified within the query string",
    )
    graph_template_id: Optional[str] = Field(
        default=None,
        description="Matched Cypher query template ID if routing to graph",
    )


class RetrievalContext(BaseModel):
    """
    Aggregates multi-source retrieval artifacts for downstream answer synthesis.
    """
    query: str = Field(
        ...,
        description="Original or coreference-resolved user query",
    )
    route: RouteDecision = Field(
        ...,
        description="Route taken during the retrieval phase",
    )
    graph_facts: List[str] = Field(
        default_factory=list,
        description="Human-readable factual statements produced by the GraphQueryEngine",
    )
    retrieved_chunks: List[VectorSearchResult] = Field(
        default_factory=list,
        description="Dense text chunks retrieved from pgvector",
    )
    cited_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Unique chunk IDs cited either in graph relationship provenance or vector hits",
    )
    latency_ms: Dict[str, float] = Field(
        default_factory=dict,
        description="Timing breakdown in milliseconds across routing, graph, and vector phases",
    )
    subgraph: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Traversed graph nodes and edges for inline UI visualization",
    )
    metadata_records: List[Any] = Field(
        default_factory=list,
        description="Resolved document catalog metadata records from MetadataResolver",
    )
    suppressed_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Auditable ledger of suppressed conflicting or placeholder evidence (ADR 052)",
    )
    # Phase 32 Graph-Guided Passage Hydration Telemetry
    candidate_graph_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Unique source_chunk_ids discovered in graph traversal",
    )
    selected_graph_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Ranked graph chunk IDs chosen for substantive passage hydration",
    )
    hydrated_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Substantive chunk IDs successfully retrieved from pgvector",
    )
    dropped_due_to_budget: List[str] = Field(
        default_factory=list,
        description="Candidate graph chunk IDs omitted due to max_graph_hydrated_passages budget cap",
    )
    # Step 32C Evidence-Gap Adaptive Passage Hydration Telemetry
    hydration_budget: int = Field(
        default=0,
        description="Selected adaptive hydration budget (0, 1, or min(|U|, 3)) based on retrieval-time evidence need",
    )
    hydration_reason: str = Field(
        default="",
        description="Machine-readable rationale for hydration budget decision",
    )


RetrievalContext.model_rebuild()

