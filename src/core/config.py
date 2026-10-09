"""
Centralized Configuration Module for Enterprise GraphRAG.

Architecture Role:
    Part of Phase 0 (Foundation & Infrastructure). Serves as the single source of truth for
    all system settings, environment variables, database URIs, API keys, and model parameters.
    Used by all downstream modules (`ingestion`, `graph`, `vector`, `router`, `synthesis`, `api`).

Inputs:
    - Environment variables or local `.env` configuration file.

Outputs:
    - Strongly typed, validated `Settings` singleton via `get_settings()`.

Design Decisions:
    - Pydantic Settings v2: Auto-casts string environment variables to typed Python primitives.
    - LRU Cache: `get_settings()` is decorated with `@lru_cache` to avoid repeated filesystem I/O
      and `.env` parsing on every invocation.
    - Fallback Defaults: Provides development defaults for local Docker container ports (Neo4j: 7687, Postgres: 5432).
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings schema.
    
    Reads from .env file or environment variables automatically.
    """

    # --------------------------------------------------------------------------
    # 1. LLM Gateway & Model Configuration (OpenRouter / NVIDIA NIM)
    # --------------------------------------------------------------------------
    llm_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="Base URL for OpenAI-compatible LLM endpoint (OpenRouter, NVIDIA NIM, etc.)",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for the LLM gateway service",
    )
    extraction_model: str = Field(
        default="meta/llama-3.2-11b-vision-instruct",
        description="Model used for entity/relationship extraction",
    )
    router_model: str = Field(
        default="meta/llama-3.2-11b-vision-instruct",
        description="Model used for question classification",
    )
    synthesis_model: str = Field(
        default="meta/llama-3.2-11b-vision-instruct",
        description="High-capability model used for grounded answer synthesis",
    )
    embedding_model: str = Field(
        default="nvidia/nemotron-3-embed-1b",
        description="Embedding model name used for pgvector dense vectors (e.g. nvidia/nemotron-3-embed-1b, openai/text-embedding-3-small)",
    )
    embedding_dimension: int = Field(
        default=2048,
        description="Dimension size of the embedding vectors (must match EMBEDDING_MODEL output length)",
    )

    # --------------------------------------------------------------------------
    # 2. Neo4j Graph Database Configuration
    # --------------------------------------------------------------------------
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Bolt protocol URI for Neo4j instance",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="graphrag_password",
        description="Neo4j password",
    )

    # --------------------------------------------------------------------------
    # 3. PostgreSQL & pgvector Database Configuration
    # --------------------------------------------------------------------------
    postgres_host: str = Field(
        default="localhost",
        description="PostgreSQL hostname",
    )
    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port",
    )
    postgres_db: str = Field(
        default="graphrag_db",
        description="PostgreSQL database name",
    )
    postgres_user: str = Field(
        default="graphrag_user",
        description="PostgreSQL username",
    )
    postgres_password: str = Field(
        default="graphrag_password",
        description="PostgreSQL password",
    )

    @property
    def postgres_async_uri(self) -> str:
        """Constructs asyncpg connection URI for PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_sync_uri(self) -> str:
        """Constructs psycopg/sync connection URI for PostgreSQL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # --------------------------------------------------------------------------
    # 4. Ingestion & API Compliance Settings
    # --------------------------------------------------------------------------
    arxiv_delay_seconds: float = Field(
        default=3.0,
        description="Polite rate limit delay between successive arXiv API requests (seconds)",
    )
    arxiv_user_agent: str = Field(
        default="Enterprise-GraphRAG-Research/1.0 (contact: research@enterprise.local)",
        description="User-Agent header identifying the client for arXiv API requests",
    )
    arxiv_acknowledgment: str = Field(
        default="Thank you to arXiv for use of its open access interoperability.",
        description="Mandatory arXiv open-access data attribution statement",
    )
    semantic_scholar_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for Semantic Scholar API for higher rate limits",
    )

    # --------------------------------------------------------------------------
    # 5. Retrieval & Precision Filtering Settings (ADR 033)
    # --------------------------------------------------------------------------
    focused_top_k: int = Field(
        default=2,
        description="Max vector chunks returned for focused factual queries to maximize context precision",
    )
    thematic_top_k: int = Field(
        default=5,
        description="Max vector chunks returned for thematic, landscape, or broad overview queries",
    )
    relevance_score_threshold: float = Field(
        default=0.72,
        description="Minimum cosine similarity score threshold to discard distractor passages",
    )

    # --------------------------------------------------------------------------
    # 6. Application Server & Runtime Settings
    # --------------------------------------------------------------------------
    app_host: str = Field(
        default="0.0.0.0",
        description="Host interface for FastAPI server",
    )
    app_port: int = Field(
        default=8000,
        description="Port for FastAPI server",
    )
    debug: bool = Field(
        default=False,
        description="Debug mode toggle",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        description="Standard request timeout in seconds for outbound HTTP / LLM gateway calls",
    )
    enable_eval_mode_override: bool = Field(
        default=False,
        description="Test-only API header override for forcing vector or hybrid retrieval during browser/evaluation runs; keep false in production.",
    )
    enable_graph_passage_hydration: bool = Field(
        default=False,
        description="Phase 32 toggle: hydrate substantive chunk texts for graph-traversed edge source_chunk_ids",
    )
    max_graph_hydrated_passages: int = Field(
        default=3,
        description="Maximum number of graph-traversed chunk passages to hydrate into prompt context",
    )
    enable_adaptive_hydration: bool = Field(
        default=False,
        description="Step 32C toggle: use evidence-gap adaptive budgeting (0, 1, or min(|U|, 3)) for graph passage hydration (rejected; keep False for 32B champion)",
    )
    enable_evidence_refinement: bool = Field(
        default=False,
        description="ADR 070: Bounded 1-pass LangGraph evidence refinement activated on detected entity/doc evidence gaps",
    )
    max_refined_facts: int = Field(
        default=3,
        description="Maximum number of graph statements merged during evidence refinement",
    )
    max_refined_chunks: int = Field(
        default=2,
        description="Maximum number of dense text passages merged during evidence refinement",
    )

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of Application Settings.
    
    Reads environment variables on first call, then reuses the cached object.
    """
    return Settings()
