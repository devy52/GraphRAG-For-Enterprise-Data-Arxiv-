[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# Detailed Design Specifications (DESIGN)

## 1. Document Chunking & Ingestion Design
The ingestion pipeline splits papers along semantic Markdown headings (`#`, `##`, `###`) and natural paragraph boundaries.
- **Target Size**: 800 characters with 100 character overlap.
- **Metadata Grounding**: Every chunk retains `document_id`, `paper_title`, `section_path`, and `chunk_id`.
- **SHA-256 Digest**: `chunk_id` is computed as `sha256(f"{document_id}:{section_path}:{index}:{text}")[:16]`.
- **Redundant Extraction Guard**: Extracted facts are persisted in `data/cache/extraction_cache.json` keyed by chunk hash, avoiding duplicate LLM extraction costs on unchanged documents.

## 2. Knowledge Graph Schema & Extraction Engine
Extracts typed facts from raw chunk text into the ontology defined in `Docs/ONTOLOGY.md`.
- **7 Entity Types**: `Paper`, `Author`, `Method`, `Dataset`, `Institution`, `Task`, `Metric`.
- **9 Relationship Types**: `CITES`, `AUTHORED_BY`, `EXTENDS`, `USES_METHOD`, `EVALUATED_ON`, `AFFILIATED_WITH`, `TARGETS_TASK`, `MEASURED_BY`, `COLLABORATED_WITH`.
- **Extraction Protocol**: Structured JSON schema output parsed into `ExtractedFact` models. Retries on validation failure up to 3 times before fallback.

## 3. Multi-Stage Entity Resolution Algorithm
Entity duplication is the primary failure mode of automated knowledge graphs. This system uses a three-tier resolution pipeline:

```
[Raw Entity Mention]
         │
         ▼
[Stage 1: Lexical Normalization]
(lowercasing, unicode NFKD, punctuation stripping, stopword trimming)
         │
         ▼
[Stage 2: Token-Level Jaccard Similarity]
(fast set overlap matching against canonical registry)
         │
         ▼  (If score < 0.85)
[Stage 3: Dense Cosine Similarity (>= 0.88)]
(embedding dot-product against canonical cluster centroids)
         │
         ▼
[Merge into Canonical Node & Append Alias]
```

## 4. Parameterized Cypher Template Catalog Design
Mitigates text-to-Cypher syntax and schema errors by restricting Neo4j execution to pre-compiled templates in `src/graph/templates.py`:

| Template ID | Traversal Pattern | Query Focus |
|---|---|---|
| `CITATION_CHAIN` | `(p:Paper)-[:CITES*1..3]->(c:Paper)` | Multi-hop paper citation trees |
| `METHOD_ANCESTRY_EXTENDS` | `(m:Method)-[:EXTENDS*1..3]->(a:Method)` | Evolutionary lineage of algorithms |
| `METHOD_BENCHMARK_COMPARISONS`| `(m:Method)-[:EVALUATED_ON]->(d:Dataset)` | Benchmark evaluation matrix |
| `CO_AUTHORSHIP_NETWORK` | `(a1:Author)-[:AUTHORED_BY]-(:Paper)-[:AUTHORED_BY]-(a2:Author)` | Collaboration network analysis |
| `PAPERS_BY_AUTHOR` | `(a:Author)<-[:AUTHORED_BY]-(p:Paper)` | Publication index per author |
| `METHODS_USED_IN_PAPER` | `(p:Paper)-[:USES_METHOD]->(m:Method)` | Algorithmic toolkit of a paper |
| `DATASETS_USED_IN_PAPER` | `(p:Paper)-[:USES_DATASET]->(d:Dataset)` | Evaluation benchmarks per paper |

Every Cypher query in the catalog explicitly projects `r.source_chunk_id` from traversed edges to enable end-to-end citation provenance.

## 5. Question Router & Session Memory Design

### 5.1 Sliding-Window Memory ($k=3$)
Maintains dialogue history over the last 3 interaction turn pairs (6 messages). Older messages are evicted to prevent context drift and memory bloat.

### 5.2 Deterministic Pronoun Coreference Resolution
Resolves ambiguous demonstratives ("that paper", "this method", "it") using regex patterns matched against the most recently mentioned salient entity in `SessionMemory`:
- `"what datasets did it use?"` $\rightarrow$ `"what datasets did 'Dense Passage Retrieval' use?"`
- `"who wrote that paper?"` $\rightarrow$ `"who wrote 'RAG Paper'?"`

### 5.3 Tri-State Intent Classification with Fallback Escalation
Queries are classified into `graph`, `vector`, or `both` using prompt few-shots or deterministic pattern dominance heuristics.
- **Escalation Rule**: If classification confidence is $< 0.70$, the router automatically escalates to `both` (hybrid route) to maximize candidate recall.

## 6. Strict Citation Validation Hard-Gate
Post-generation verification prevents citation confabulation:
1. `CitationValidator` scans generated text with regex `\[(?:chunk:\s*)?([a-zA-Z0-9_\-\.]+)\]`.
2. Verifies set membership: $\text{Citations} \subseteq \text{AllowedChunkIDs}$.
3. If an unrecognized ID appears, validation fails immediately, returning a list of `hallucinated_citations`.
4. The synthesizer feeds the diagnostic failure back to the LLM, triggering regeneration (up to 2 attempts).

## 7. Caching Architecture
Two independent caching tiers reduce latency and API expenditure:
1. **Extraction Cache**: Keyed by SHA-256 chunk hash; skips redundant entity/relation extraction.
2. **Query Response Cache**: `QueryResponseCache` in `src/core/cache.py` normalizes incoming user questions (casing, whitespace, punctuation) and caches verified `SynthesizedAnswer` objects keyed by SHA-256 query digests.

## 8. Material 3 Web Interface Design

The frontend is a zero-Node.js, single-page application built with modern HTML5, vanilla CSS implementing Google Material Design 3 tokens, and ES6 modules served natively by FastAPI (`src/api/static/`).

### 8.1 Material 3 Design Tokens & Styling
- **Tonal Color Palette**:
  - `md-sys-color-primary`: `#6750A4` (Dark mode: `#D0BCFF`)
  - `md-sys-color-on-primary`: `#FFFFFF` (Dark mode: `#381E72`)
  - `md-sys-color-surface`: `#FEF7FF` (Dark mode: `#141218`)
  - `md-sys-color-surface-container`: `#F3EDF7` (Dark mode: `#211F26`)
  - `md-sys-color-surface-container-high`: `#ECE6F0` (Dark mode: `#2B2930`)
  - `md-sys-color-outline`: `#79747E` (Dark mode: `#938F99`)
  - `md-sys-color-tertiary`: `#7D5260` (Dark mode: `#EFB8C8`)
- **Typography Scale**: Google Sans / Roboto / Inter via Google Fonts (`display-large`, `headline-medium`, `title-medium`, `body-large`, `label-medium`).
- **Elevation & Shape Tokens**:
  - Cards & Containers: `border-radius: 16px` (Medium/Large), subtle ambient box-shadows.
  - Buttons & Chips: Full-pill `border-radius: 9999px`, active ripple and hover state layers.

### 8.2 Component Hierarchy & Views
1. **Top App Bar**:
   - Title: "Enterprise GraphRAG" with status badge.
   - Live Connectivity Pills: PostgreSQL (Green/Red), Neo4j (Green/Red).
   - Cache Metrics: Real-time hit rate and cached query count.
2. **Navigation Rail**:
   - Tab 1: **Chat Workspace** (Natural language query interface, response cards, route tags).
   - Tab 2: **Neo4j Topology** (Full-screen interactive graph explorer with search, zoom, pan).
   - Tab 3: **System Telemetry** (API latency breakdowns, model configuration, arXiv attribution).
3. **Interactive Graph Visualizer Canvas**:
   - Force-directed physics canvas (Vis-Network via CDN).
   - Node Color Scheme: `Paper` (Blue `#1E88E5`), `Method` (Purple `#8E24AA`), `Dataset` (Amber `#FB8C00`), `Author` (Emerald `#43A047`), `Topic` (Coral `#F4511E`).
   - Click-to-Inspect: Clicking a node displays canonical name, ontology type, and alias list.
   - Edge Hover: Displays relationship type (e.g. `EXTENDS`, `USES_DATASET`, `CITES`) and confidence score.
4. **Citation Grounding Inspector**:
   - Interactive citation tags `[chunk_id]` within the synthesized response.
   - Clicking a citation opens a modal/sheet displaying the raw source passage, paper title, and section path.

## 9. Customizable Ingestion Orchestrator & M3 Ingestion Dialog

### 9.1 Background Ingestion Architecture
The `IngestionOrchestrator` manages asynchronous batch ingestion tasks within the FastAPI service without external brokers:
- **Thread-Safe State Machine**: Tracks status (`idle`, `running`, `completed`, `failed`), active stage (`harvesting`, `chunking`, `embedding`, `extracting`, `resolving`, `writing`), percentage completion, and circular log buffer.
- **Asynchronous Execution**: Launched via `fastapi.BackgroundTasks` or `asyncio.create_task()`.
- **Idempotency & Resilience**: Supports cancellation checks, per-chunk error capture, and automatic cache bypass/refresh.

### 9.2 Material 3 Ingestion Dialog UX
- **Launch Trigger**: "Ingest Corpus" button in Top App Bar with M3 tonal styling (`cloud_upload` icon).
- **M3 Dialog Surface**:
  - **Mode Selector**: Segmented button or radio chips: "Harvest from arXiv" vs. "Populate Existing Chunks".
  - **Configuration Form**:
    - Query field (default: `"retrieval-augmented generation"`).
    - Paper harvest limit (default: `50`).
    - Chunk batch limit (slider / number input).
    - Pipeline switches: "Populate Neo4j" (checked), "Populate pgvector" (checked).
  - **Live Progress Pane**:
    - Linear indeterminate/determinate progress indicator (`md-linear-progress`).
    - Active stage badge with animated pulse.
    - Terminal-style scrollable live log viewer.
  - **Action Controls**: "Start Ingestion", "Close / Dismiss".
