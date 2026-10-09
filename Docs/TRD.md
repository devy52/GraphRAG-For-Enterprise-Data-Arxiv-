[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# Technical Requirements Document (TRD)

## 1. System Overview & Technology Stack

The Enterprise GraphRAG architecture is built entirely in modern Python ($\ge 3.11$) using containerized database backends, standard open protocols, and an OpenAI-compatible gateway abstraction.

| Layer | Component | Specification |
|---|---|---|
| **Runtime & Language** | Python | CPython 3.11+ (tested on Python 3.14 venv), PEP 8, Pydantic v2 |
| **API Framework** | FastAPI | Asynchronous ASGI, Uvicorn, CORS, Lifespan connection management |
| **Graph Database** | Neo4j Community v5 | Bolt protocol, APOC Core plugins, Cypher 5, Uniqueness Constraints |
| **Vector Database** | PostgreSQL 16 + pgvector | `vector(1536)`, HNSW index (`vector_cosine_ops`), SQLAlchemy 2.0 Async |
| **LLM Gateway** | OpenAI Client | Unified OpenAI-compatible endpoint (OpenRouter / NVIDIA NIM) |
| **Testing & CI** | Pytest | `pytest-asyncio`, 100% offline self-sufficient mock fallbacks |
| **Caching Layer** | In-Memory LRU Cache | SHA-256 canonical query hashing, capacity-bounded eviction |
| **Web Interface** | Material 3 Web App | Vanilla HTML5, M3 CSS tokens, ES6 modules, Vis-Network graph canvas via FastAPI static mount |

## 2. Infrastructure & Database Schemas

### 2.1 Neo4j Graph Database
- **Connection URI**: `bolt://localhost:7687`
- **Authentication**: Native username/password credentials.
- **Constraints & Indexes**:
  - Uniqueness constraints on `(n:Label {name: string})` for all 7 entity types (`Paper`, `Author`, `Method`, `Dataset`, `Institution`, `Task`, `Metric`).
  - Indexing on `source_chunk_id` edge property.
- **Write Policy**: 100% idempotent Cypher writes via `MERGE`. Raw node `CREATE` statements are strictly forbidden.

### 2.2 PostgreSQL + pgvector
- **Connection URI**: `postgresql+asyncpg://user:pass@localhost:5432/graphrag_db`
- **Table Definition**: `document_chunks`
  - `chunk_id VARCHAR(64) PRIMARY KEY`: Unique SHA-256 derived identifier.
  - `document_id VARCHAR(64) NOT NULL`: Parent paper/document identifier.
  - `paper_title TEXT NOT NULL`: Grounding paper title.
  - `section_path TEXT NOT NULL`: Hierarchical document section heading.
  - `text TEXT NOT NULL`: Chunk text content (target 800 chars, 100 overlap).
  - `entity_ids JSONB DEFAULT '[]'`: Resolved canonical entities appearing in chunk.
  - `embedding vector(1536)`: Dense text embedding vector.
  - `created_at TIMESTAMP WITH TIME ZONE`: Record insertion timestamp.
- **Index Specification**:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_document_chunks_hnsw
  ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
  ```

## 3. API Contract Specifications

### 3.1 `POST /query`
- **Request Payload**:
  ```json
  {
    "query": "string (1-1000 chars)",
    "session_id": "string (optional)",
    "top_k": 5,
    "use_cache": true
  }
  ```
- **Response Payload**:
  ```json
  {
    "query": "string",
    "answer": "string with [chunk_id] citations",
    "route_taken": "graph | vector | both",
    "citations": ["chunk_01", "chunk_02"],
    "is_grounded": true,
    "from_cache": false,
    "graph_facts": ["Fact statement [chunk_01]"],
    "latency_breakdown_ms": {
      "routing_ms": 2.1,
      "graph_ms": 11.4,
      "synthesis_ms": 18.2,
      "total_request_ms": 32.5
    }
  }
  ```

### 3.2 `GET /health`
- **Response**:
  ```json
  {
    "status": "healthy | degraded",
    "neo4j_connected": true,
    "postgres_connected": true,
    "timestamp": "2026-09-30T10:00:00Z"
  }
  ```

### 3.3 `GET /stats`
- **Response**:
  ```json
  {
    "total_requests": 142,
    "cache_hits": 89,
    "cache_misses": 53,
    "cache_hit_rate": 0.6268,
    "cached_entries": 53,
    "models": {
      "extraction_model": "nvidia/nemotron-3-super-120b-a12b",
      "router_model": "nvidia/nemotron-3-super-120b-a12b",
      "synthesis_model": "nvidia/nemotron-3-super-120b-a12b",
      "embedding_model": "nvidia/nemotron-3-embed-1b",
      "embedding_dim": 2048
    },
    "infrastructure": {
      "neo4j_uri": "bolt://localhost:7687",
      "postgres_target": "localhost:5432/graphrag",
      "cache_backend": "in_memory_lru"
    }
  }
  ```

### 3.4 `GET /graph/subgraph`
- **Query Parameters**:
  - `limit`: integer (default 100, max 300) — maximum number of relationships to return.
  - `entity_type`: string (optional) — filter nodes by ontology entity type (`Paper`, `Method`, `Dataset`, `Author`, `Topic`).
- **Response Payload**:
  ```json
  {
    "nodes": [
      {
        "id": "RAG-Sequence",
        "label": "RAG-Sequence",
        "type": "Method",
        "aliases": ["Retrieval-Augmented Generation"]
      }
    ],
    "edges": [
      {
        "source": "RAG-Sequence",
        "target": "Natural Questions",
        "type": "USES_DATASET",
        "source_chunk_id": "chunk_arxiv_2005_11401_000",
        "confidence": 0.95
      }
    ],
    "total_nodes": 45,
    "total_edges": 68
  }
  ```

- `POST /ingest`: Triggers asynchronous background ingestion.
  - Request:
    ```json
    {
      "mode": "existing_corpus",
      "query": "retrieval-augmented generation",
      "paper_limit": 50,
      "chunk_limit": 115,
      "populate_neo4j": true,
      "populate_pgvector": true
    }
    ```
  - Response (202 Accepted):
    ```json
    {
      "status": "running",
      "stage": "extracting",
      "message": "Ingestion initiated in background",
      "progress_pct": 0.0
    }
    ```

- `GET /ingest/status`: Polls active ingestion status, progress percentage, stage, and recent logs.
  - Response (200 OK):
    ```json
    {
      "status": "running",
      "stage": "extracting",
      "progress_pct": 42.5,
      "current_item": 49,
      "total_items": 115,
      "message": "Extracting facts from chunk 49/115",
      "logs": ["Processing chunk 48...", "Processing chunk 49..."]
    }
    ```

## 4. Latency Budgets & Performance SLOs

| Pipeline Stage | Target Latency (p50) | Target Latency (p95) |
|---|---|---|
| Query Routing | $< 10$ ms | $< 25$ ms |
| Graph Query Traversal (Neo4j) | $< 15$ ms | $< 35$ ms |
| Vector Similarity Search (pgvector) | $< 12$ ms | $< 25$ ms |
| Answer Synthesis (LLM) | $< 400$ ms | $< 650$ ms |
| Citation Hard-Gate Validation | $< 2$ ms | $< 5$ ms |
| **Total End-to-End Query** | **$< 450$ ms** | **$< 700$ ms** |

## 5. Security, Invariants & Error Handling

1. **Injection Prevention**: Zero unconstrained text-to-Cypher. All graph queries execute parameterized Cypher templates (`CYPHER_TEMPLATES`) where parameters are passed separately from query strings.
2. **Provenance Invariant**: Every graph relationship and every vector chunk record MUST carry a valid `source_chunk_id`.
3. **Hard Gate Guarantee**: Answers containing hallucinated citations are blocked at the validator tier and regenerated; non-compliant answers are never served.
4. **Offline Resilience**: When LLM gateway credentials are absent or dummy, deterministic fallback mechanisms activate automatically, allowing 100% offline test execution.

## 6. External API Compliance & Rate Limiting
1. **Mandatory Attribution**: All public APIs (`GET /`, `GET /stats`) and documentation must render: *"Thank you to arXiv for use of its open access interoperability."*
2. **Strict Serial Rate Limiting**: The `PaperCollector` enforces a hard asynchronous sleep of $\ge 3.0$ seconds between consecutive calls to `https://export.arxiv.org/api/query`, restricted to a single connection.
3. **No PDF/Source Storage**: The ingestion layer parses Atom XML metadata and abstracts only. Under no circumstances are full e-print PDFs or source TeX archives downloaded, stored, or distributed.
4. **Non-Endorsement Policy**: Systems and interfaces must not use arXiv names, logos, or web branding in any manner implying endorsement.
