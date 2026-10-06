[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md)
---

# Architecture

## Data flow

```
Documents
   │
   ├─► Chunking ─────────────────────────────┐
   │                                          │
   ▼                                          ▼
Entity/Relationship Extraction (Claude)   Embedding (pgvector)
   │                                          │
   ▼                                          │
Entity Resolution (dedupe/alias)             │
   │                                          │
   ▼                                          │
Neo4j (MERGE, idempotent)                     │
   │                                          │
   └──────────────┬───────────────────────────┘
                   │  shared chunk_id links graph ↔ vectors
                   ▼
              Question Router
             /               \
      graph path         vector path
   (parameterized          (HNSW search,
    Cypher templates)       ef_search tuned)
             \               /
              ▼             ▼
         Merge + label sources
                   │
                   ▼
         Citation validation
         (every claim → real chunk_id, else reject & regenerate)
                   │
                   ▼
            FastAPI response
```

## Components

### 1. Extraction pipeline
- Input: chunked documents
- Output: `(entity_type, canonical_name, relationship_type, source_chunk_id, confidence)`
- Schema-validated Claude calls; retry on validation failure
- Cache by document hash — never re-extract an unchanged document
- Cost budget checked per-document before full-corpus runs

### 2. Entity resolution
- Normalize → embedding-similarity match above tuned threshold → alias list on node
- This is the step most likely to get skipped. It doesn't get skipped here.

### 3. Neo4j graph store
- Fixed ontology: 5–10 entity types, 8–15 relationship types (see `ONTOLOGY.md`)
- All writes use `MERGE`, never `CREATE` — ingestion must be safely re-runnable
- Every edge carries `source_chunk_id`

### 4. pgvector store
- Same chunks as the graph, embedded with metadata: `document_id`, `section_path`,
  `date`, `entity_ids` mentioned
- HNSW index; `ef_search` tuned against a labeled recall@k set before anything
  is built on top of it

### 5. Router
- Cheap model call, few-shot, returns an enum: `graph | vector | both`
- Low-confidence → run both paths, merge
- Routing rule of thumb:
  - **graph** → connections, multi-hop chains, cross-entity comparisons, aggregations
  - **vector** → definitions, policy lookups, single-fact questions
- Every routing decision logged (question + outcome) — needed for Phase 5, can't
  be reconstructed after the fact

### 6. Graph query execution
- Extract entities from the question → resolve to node IDs → run a
  **parameterized** Cypher template
- Model never emits raw Cypher. Template library keyed by query type; model
  fills parameters only.

### 7. Merge + citation
- Graph paths converted to readable statements before hitting the prompt
- Dedup across graph + vector results; context assembled with explicit
  `[graph]` / `[retrieved]` labels
- One citation required per claim; each citation must resolve to a chunk_id
  that was actually retrieved, or the answer is rejected and regenerated

### 8. API
- FastAPI ASGI server exposing `/query`, `/health`, `/stats`, and `/graph/subgraph`.
- Returns: answer, citations, route taken, graph facts, and latency breakdown.

### 9. Material 3 Web Interface
- Zero-Node, single-page web app built with vanilla HTML5, Google Material Design 3 CSS tokens, and ES6 JavaScript.
- Direct FastAPI static asset serving at `http://localhost:8000/`.
- Features: Dual Chat & Graph view, real-time route badge inspection, interactive force-directed canvas for Neo4j topology exploration, raw citation chunk drawer, and customizable Ingestion Dialog with live progress telemetry.

### 10. Ingestion Orchestrator Service
- Asynchronous pipeline worker managing background ingestion runs without external message brokers.
- Orchestrates `arXivCollector`, `TextChunker`, `VectorStore`, `GraphExtractor`, `EntityResolver`, and `GraphWriter`.
- Exposes real-time status, progress percentages, active stages, and log streams via `GET /ingest/status`.

## Decisions

1. **Corpus** — curated arXiv papers (RAG/LLM retrieval subfield), see README
2. **Router model** — model call via OpenRouter (or NVIDIA NIM build), few-shot
   → enum (`graph | vector | both`). Any small/cheap instruction-following model
   works; swap freely without touching the router's logic or prompt structure.
3. **Neo4j hosting** — local Docker Compose for build/dev (free, no account
   setup, matches existing Docker usage). Migrate to Neo4j AuraDB free tier
   only if/when this needs a public-facing demo.
4. **Embedding model** — open, still to pick. Check what `evalkit` uses first
   so the two projects share one embedding choice instead of two.
