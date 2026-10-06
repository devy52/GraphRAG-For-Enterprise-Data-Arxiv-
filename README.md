# Enterprise Knowledge Graph RAG (GraphRAG)

A production-grade, hybrid retrieval-augmented generation system combining a **Neo4j property graph** with a **pgvector semantic store**. Designed for enterprise technical and scientific literature (e.g. arXiv research papers), it deterministically routes relational / multi-hop questions to graph traversals and definitional questions to dense vector search, then merges both into a single grounded answer with strict citation validation.

---

## Benchmark Results (vs. Plain Vector RAG — Authoritative 50Q Benchmark)

Evaluated across the canonical 50-question benchmark (`data/benchmark_v2_dataset.jsonl`, SHA-256: `88fc85fc1af4`) under identical LLM inference (`Qwen2.5-7B-Instruct`, `temperature=0.0`):

| Evaluation Metric | Plain Vector Baseline | Hybrid GraphRAG (3-Run Mean) | Absolute Delta | Relative Gain | Research Assessment |
|---|:---:|:---:|:---:|:---:|---|
| **Overall Fact Score** | 0.5417 | **0.8042 ± 0.0150** | **+0.2625** | **+48.5%** | 🟢 Observed Accuracy Gain |
| **Strict Success Rate (Answerable)** | 14/40 (35.0%) | **26.3 ± 1.5 / 40 (65.8%)** | **+30.8%** | **+87.9%** | 🟢 Increased Strict Passes |
| **Substantive Chunk Recall** | 0.2821 | **0.6538** | **+0.3717** | **+131.8%** | 🟢 Chunk Coverage Gain via Hydration |
| **Unified Evidence Recall** | 0.3083 | **0.6708** | **+0.3625** | **+117.6%** | 🟢 Expanded Evidence Ledger Coverage |
| **3-Hop Relational Fact Score** | 0.4000 | **0.8778 ± 0.0509** | **+0.4778** | **+119.5%** | 🟢 Multi-Hop Evidence Recovery |
| **2-Hop Relational Fact Score** | 0.6000 | **0.8000** | **+0.2000** | **+33.3%** | 🟢 2-Hop Bridge Recovery |
| **Out-of-Scope Refusal Accuracy** | **100.0%** (10/10) | **100.0%** (10/10) | 0.0% | Tied | 🟢 Consistent Out-of-Scope Refusal |
| **Citation Hallucination Rate** | **0.0%** | **0.0%** | 0.0% | Tied | 🟢 Zero Invalid Citations (AST Verified) |
| **Mean Context Tokens** | **250 tokens** | 598 tokens | +348 tokens | — | 🟡 Accepted Trade-Off for Multi-Hop Evidence |

> [!NOTE]
> **3-Run Repeatability Study & System Classification (Phase 33D)**:
> - **3-Run Performance Overview**: Fact score **0.8042 ± 0.0150** (range [0.7917, 0.8208]), Strict success **26.3 ± 1.5 / 40** (65.8%, range [25, 28]), Mean of run-level P50 medians **4,311.4 ms** (individual runs: 4112.7, 5043.9, 3777.7 ms, demonstrating provider queue variability).
> - **Retrieval & Evidence Determinism**: **Identical across the three observed runs (50/50 candidate chunks, graph facts, and hydrated passages)**. Substantive recall (0.6538) and unified recall (0.6708) were invariant across this sample.
> - **Per-Question Stability**: **88.0% (44/50 questions)** produced identical fact scores across the three runs. The observed end-to-end variance occurs downstream of deterministic retrieval/evidence construction, with the audit attributing the six unstable cases to answer-generation phrasing variation.
> - **Latency Decomposition**: Remote NIM generation is the largest measured median latency component (1979.1 ms, ~52.4%), while local DB retrieval (411.9 ms) and passage hydration (8.2 ms) contribute substantially less (~11.1% combined); the remaining ~36.5% accounts for routing, context assembly, and network round-trips.
> - **Final System Classification**: **Research Champion / Release Candidate (Quantified Generator Variance)**. Context expansion (~598 tokens) is documented and accepted as an engineering trade-off for multi-hop evidence recovery (ADR 064).

---

## Evaluation Framework & Independent Testing

### In-Repo Evaluation Framework (`evalkit`)
This benchmark was conducted using **`evalkit`** (and its compatibility wrapper `evalharness`), a specialized in-repo evaluation framework designed to evaluate GraphRAG relational retrieval. `evalkit` provides:
- **Relational Path & Evidence Accounting**: Evaluates multi-hop graph traversals against typed evidence ledgers rather than unstructured text alone.
- **Strict Citation AST Validation**: Verifies that citations map directly to retrieved chunks, rejecting fabricated IDs.
- **Negation & Refusal Calibration**: Evaluates out-of-scope refusals without false hallucination penalties.
- **Deterministic Stage Profiling**: Separates local database latency from remote model generation times.

> **Note on `evalkit` Publishing**: `evalkit` is currently maintained as an in-repo module for this project. While it may be considered for packaging and publication as a separate open-source utility in future work, it currently remains internal to this codebase.

### Testing with External Frameworks (Ragas, DeepEval, TruLens)
Others can independently test and benchmark against this system using other standard evaluation frameworks:
- The authoritative 50-question benchmark dataset is exported in standard JSONL format at [`data/benchmark_v2_dataset.jsonl`](data/benchmark_v2_dataset.jsonl) with ground-truth facts, reference answers, and typed gold chunk evidence.
- An adapter script ([`eval_adapter.py`](eval_adapter.py)) formats system outputs into standard schemas compatible with **Ragas**, **DeepEval**, or **TruLens**.
- To test with an alternative framework:
  ```bash
  python eval_adapter.py --framework ragas --dataset data/benchmark_v2_dataset.jsonl
  ```

---

## Architecture & Data Flow

```
                             [arXiv / Semantic Scholar Papers]
                                             │
                                             ▼
                                     [Document Chunker]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
         [LLM Entity/Rel Extractor]                       [Text Embeddings]
                       │                                           │
                       ▼                                           ▼
             [Entity Resolution]                           [pgvector (HNSW)]
          (dedupe + alias linking)                                 │
                       │                                           │
                       ▼                                           │
             [Neo4j Graph Store]                                   │
           (idempotent MERGE writes)                               │
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │ (Linked via source_chunk_id)
                                             ▼
                                     [Question Router]
                                    /                 \
                             [Graph Path]         [Vector Path]
                          (Parameterized Cypher)  (Cosine Similarity)
                                    \                 /
                                     ▼               ▼
                                [Merge & Source Labelling]
                                             │
                                             ▼
                                 [Citation Validator]
                        (verifies all citations against retrieved IDs)
                                             │
                                             ▼
                                   [FastAPI /query API]
```

---

## Key Technologies & Techniques

| Component | Technology | Rationale |
|---|---|---|
| **Graph Store** | **Neo4j Community v5 + APOC** | Native property graph indexing, fast multi-hop traversals, edge-level `source_chunk_id` attributes. |
| **Vector Store** | **PostgreSQL + pgvector** | HNSW index for ultra-fast dense text similarity search. |
| **LLM Gateway** | **OpenRouter / NVIDIA NIM** | OpenAI-compatible endpoint compatibility; decoupled from single-vendor lock-in. |
| **Graph Queries** | **Parameterized Cypher Templates** | **Zero raw LLM-generated Cypher**. Completely eliminates Cypher injection and syntax hallucinations. |
| **Citation Validation** | **Deterministic AST/Regex Validator** | Hard gate that rejects and regenerates answers citing non-retrieved `chunk_id`s. |
| **API Framework** | **FastAPI + Uvicorn** | High-performance asynchronous REST API with automatic OpenAPI documentation. |
| **Caching Tier** | **Dual-Tier Cache** | SHA-256 chunk hash extraction cache + normalized question cache to cut LLM costs by >80%. |

---

## Documentation & Reading Guide

For complete, audit-grade architectural clarity, navigate the documentation set in sequential order:

1. **[Product Requirements (PRD)](Docs/PRD.md)**: Problem statement, user personas, functional requirements, and success metrics.
2. **[Technical Requirements (TRD)](Docs/TRD.md)**: Hardware/cloud requirements, database schemas, API specs, and latency SLOs.
3. **[Ontology Definition](Docs/ONTOLOGY.md)**: 7 entity types and 9 relationship types governing knowledge graph extraction.
4. **[System Architecture](Docs/ARCHITECTURE.md)**: High-level dual-store architecture and core component roles.
5. **[Detailed Design](Docs/DESIGN.md)**: Algorithmic specifications (multi-stage entity resolution, Cypher template catalog, confidence escalation).
6. **[Sequence Flows](Docs/FLOWS.md)**: Mermaid sequence diagrams for ingestion, retrieval, citation verification, and health checks.
7. **[Codebase Map](Docs/CODEBASE_MAP.md)**: Exhaustive directory index, file-by-file inventory, and public symbol directory.
8. **[Architecture Decision Records](Docs/DECISIONS.md)**: Complete decision log (ADR 001–020) with trade-off matrices.
9. **[Tasks & Handoff Tracker](Docs/TASKS.md)**: Phase-by-phase implementation status and multi-agent resume state.

---

## Repository Structure

```
GraphRAG-For-Enterprise-Data/
├── Docs/                           # Canonical project documentation & specifications
│   ├── ARCHITECTURE.md             # High-level architecture & system design
│   ├── CODEBASE_MAP.md             # Exhaustive file directory & symbol inventory
│   ├── DECISIONS.md                # Architecture Decision Records (ADR 001–020)
│   ├── DESIGN.md                   # Detailed design & algorithmic specifications
│   ├── FLOWS.md                    # Mermaid sequence diagrams for all major workflows
│   ├── ONTOLOGY.md                 # Entity and relationship ontology definition
│   ├── PRD.md                      # Product Requirements Document
│   ├── PROJECT_SPEC.md             # Original project scope & checklist
│   ├── TASKS.md                    # Phase-by-phase implementation tracker
│   └── TRD.md                      # Technical Requirements Document
├── data/                           # Local database storage & extraction caches
│   ├── cache/                      # Extraction & pipeline caches
│   ├── neo4j/                      # Neo4j persistent volumes & plugins
│   └── postgres/                   # PostgreSQL/pgvector database files
├── src/                            # Production source code
│   ├── api/                        # FastAPI application routes, schemas & lifespan
│   ├── core/                       # Settings, structured logging & response cache
│   ├── eval/                       # Stratified benchmark dataset, runner & reporter
│   ├── graph/                      # Neo4j extractor, resolver, writer & query engine
│   ├── ingestion/                  # arXiv & Semantic Scholar collectors + chunker
│   ├── memory/                     # Sliding-window session buffer (k=3) & coreference
│   ├── router/                     # Intent classifier & central retrieval coordinator
│   ├── synthesis/                  # Grounded synthesizer & citation validation hard gate
│   └── vector/                     # pgvector schema, embeddings indexer & tuner
├── tests/                          # Automated test suite (43/43 passing 100% offline)
├── docker-compose.yml              # Local container configuration for Neo4j & PostgreSQL
├── pyproject.toml                  # Python packaging & tool configurations
└── requirements.txt                # Pinned production & dev dependencies
```

---

## Quickstart Guide

### 1. Prerequisites
- **Python 3.11+**
- **Docker Desktop** (for local Neo4j and PostgreSQL containers)

### 2. Clone & Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/GraphRAG-For-Enterprise-Data.git
cd GraphRAG-For-Enterprise-Data

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e .
```

### 3. Start Database Containers
```bash
# Start Neo4j (v5+APOC) and PostgreSQL (pgvector) in background
docker compose up -d
```
*Note: Storage volumes are mounted under `./data/` on the current drive.*

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your LLM credentials:
```bash
cp .env.example .env
```
Key settings to configure in `.env`:
```ini
# Gateway: Compatible with NVIDIA NIM, OpenRouter, vLLM, or Ollama
LLM_BASE_URL="https://integrate.api.nvidia.com/v1"
LLM_API_KEY="your_api_key_here"

# Model Selection for the 3 Engines (Free Endpoints on NVIDIA NIM)
EXTRACTION_MODEL="nvidia/nemotron-3-super-120b-a12b"
ROUTER_MODEL="nvidia/nemotron-3-super-120b-a12b"
SYNTHESIS_MODEL="nvidia/nemotron-3-super-120b-a12b"

# Dense Embeddings & Vector Dimension
# NOTE: EMBEDDING_DIMENSION must match the embedding model output dimension!
# (e.g. 2048 for nemotron-3-embed-1b, 1536 for text-embedding-3-small, 1024 for bge-large)
EMBEDDING_MODEL="nvidia/nemotron-3-embed-1b"
EMBEDDING_DIMENSION=2048

# Database defaults (matches docker-compose.yml)
NEO4J_URI="bolt://localhost:7687"
NEO4J_PASSWORD="graphrag_password"
POSTGRES_PASSWORD="graphrag_password"
```

> [!TIP]
> **Gateway & Model Flexibility**: You can set `LLM_BASE_URL` to any OpenAI-compatible provider (NVIDIA NIM, OpenRouter, local vLLM). When swapping `EMBEDDING_MODEL`, always verify its output vector dimension and update `EMBEDDING_DIMENSION` before initializing the database tables.

### 5. Run Ingestion Pipeline
Fetch papers, extract knowledge graph triples, and build the vector index:
```bash
python -m src.ingestion.collector --query "retrieval-augmented generation" --limit 50
```

### 6. Start the FastAPI API Server
```bash
uvicorn src.api.main:app --reload --port 8000
```
Interactive OpenAPI documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 7. Run Authoritative Benchmark (Evalkit)
Execute the multi-track benchmark (RAG quality, graph traversal utilization, retrieval ranking, and text similarity) using the authoritative unified `evalkit` engine (with backward-compatible `evalharness` alias) and serverless Fireworks DeepSeek V4.1 Flash judge:
```bash
python run_evalkit.py --limit 10
```
Reports and metrics are generated under `data/evalkit_report.md` and `data/evalkit_results.json`:

| Track | Metric | Benchmark Score | Description |
|:---|:---|:---|:---|
| **Retrieval Ranking** | `recall_at_k` | **0.875** | Fraction of ground-truth chunks retrieved in top-$k$ |
| | `precision_at_k` | **0.188** | Ground-truth chunk precision within top-$k$ |
| | `mrr` | **0.250** | Mean Reciprocal Rank of first relevant passage |
| | `ndcg_at_k` | **0.587** | Position-discounted retrieval ranking gain |
| | `chunk_utilization` | **0.365** | Lexical utilization rate of retrieved chunks |
| **RAG Generation** | `faithfulness` | **0.740** | Unhallucinated factual grounding |
| | `context_precision` | **0.310** | Ratio of relevant passages in retrieved context |
| | `context_recall` | **0.300** | Reference facts retrieved in context |
| | `answer_relevancy` | **0.390** | Semantic alignment with user question |
| | `answer_correctness`| **0.350** | Factual agreement with reference answer |
| **Graph Traversal** | `graph_utilization_rate` | **0.468** | Traversed graph facts synthesized in answer |
| | `global_diversity` | **0.894** | Lexical breadth across graph communities |
| **Text Similarity** | `token_f1` | **0.321** | SQuAD-style token overlap with reference |
| | `rouge_l` | **0.233** | Longest common subsequence score |

### 8. Evaluation V2 Integrity Benchmark & Dataset Validation
To validate dataset fingerprinting and run the anti-contamination Evaluation V2 suite:
```bash
python scripts/validate_benchmark_v2_dataset.py
python scripts/audit_eval_v2.py
python -m pytest tests/test_eval_v2.py tests/test_benchmark_integrity.py
```

---

## API Usage

### Query Endpoint (`POST /query`)

**Request:**
```json
{
  "question": "Which methods extend RAG-Sequence and what datasets were they evaluated on?",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Iterative-RAG extends RAG-Sequence by introducing multi-step retrieval loops [chunk_rag_042]. It was evaluated on Natural Questions [chunk_rag_043] and HotpotQA [chunk_rag_045].",
  "route": "graph",
  "citations": [
    {
      "chunk_id": "chunk_rag_042",
      "paper_title": "Iterative Retrieval-Augmented Generation",
      "section": "2.1 Architecture"
    },
    {
      "chunk_id": "chunk_rag_043",
      "paper_title": "Iterative Retrieval-Augmented Generation",
      "section": "4.1 Datasets"
    }
  ],
  "latency_ms": 485
}
```

---

## Customization Guide

- **Modifying the Ontology**: Edit [Docs/ONTOLOGY.md](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/Docs/ONTOLOGY.md) to add new entity types (e.g. `Benchmark`, `Metric`) or relationship types.
- **Customizing Query Templates**: Add Cypher queries to `src/graph/templates.py` to support domain-specific graph traversal queries.
- **Changing LLM / Embeddings**: Adjust `LLM_BASE_URL` and `EMBEDDING_MODEL` in `.env`.
- **Reviewing Technical Decisions**: Check [Docs/DECISIONS.md](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/Docs/DECISIONS.md) for full trade-off analyses behind every architectural choice (ADR 001–020).

---

## Acknowledgments & Open Access Compliance

> **"Thank you to arXiv for use of its open access interoperability."**

This system operates in strict accordance with the arXiv API Terms of Use:
- **Polite Rate Limiting**: All requests are strictly throttled to at most one request every 3.0 seconds (`ARXIV_DELAY_SECONDS=3.0`) over a single sequential connection.
- **No Redistribution of E-Prints**: The system never stores or serves arXiv PDF e-prints or source files; only open-access metadata and abstracts are indexed for retrieval.
- **Independent Project**: This project is independent research and is not affiliated with, branded by, or endorsed by arXiv.

---

## License
MIT License. Free for enterprise and research use.
