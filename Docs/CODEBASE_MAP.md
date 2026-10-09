[← README](../README.md) | [PRD](PRD.md) | [TRD](TRD.md) | [Design](DESIGN.md) | [Architecture](ARCHITECTURE.md) | [Flows](FLOWS.md) | [Codebase Map](CODEBASE_MAP.md) | [Decisions](DECISIONS.md) | [Tasks](TASKS.md) | [Scorecard](BENCHMARK_SCORECARD.md)
---

# Codebase Map & Module Directory

A comprehensive directory and file-by-file index detailing the exact location, purpose, exported symbols, inputs, outputs, and architectural roles across the entire enterprise repository.

---

## 1. Directory Tree Overview

```
GraphRAG-For-Enterprise-Data/
├── Docs/                           # Canonical project documentation & specifications
│   ├── ARCHITECTURE.md             # High-level architecture & system design
│   ├── BENCHMARK_SCORECARD.md      # Comprehensive benchmark scorecard compiling & comparing all versions & techniques
│   ├── CODEBASE_MAP.md             # Exhaustive file directory & symbol inventory (this file)
│   ├── DECISIONS.md                # Architecture Decision Records (ADR 001–068)
│   ├── DESIGN.md                   # Detailed design & algorithmic specifications
│   ├── FLOWS.md                    # Mermaid sequence diagrams for all major workflows
│   ├── ONTOLOGY.md                 # Entity and relationship ontology definition
│   ├── PRD.md                      # Product Requirements Document
│   ├── PROJECT_SPEC.md             # Initial project scope and checklist
│   ├── TASKS.md                    # Multi-agent handoff tracker & task checklists
│   └── TRD.md                      # Technical Requirements Document
├── data/                           # Local storage volumes & caching
│   ├── cache/                      # Extraction & pipeline caches
│   │   └── extraction_cache.json   # Chunk SHA-256 fact extraction cache
│   ├── abcd_ablation_audit.jsonl   # Per-question audit records across Modes A, B, C, D
│   ├── abcd_ablation_report.md     # Markdown side-by-side performance table & causal triage
│   ├── abcd_ablation_results.json  # Comprehensive machine-readable ABCD evaluation metrics
│   ├── benchmark_v2_dataset.jsonl  # Authoritative 50Q dataset with typed gold evidence & supports
│   ├── gold_evidence_audit.json    # Machine-readable Step 2 audit across chunks, metadata, and graph
│   ├── gold_evidence_audit.md      # Comprehensive Step 2 audit documentation with G1/G2 determinations
│   ├── run2_metadata_audit.jsonl   # Per-question audit records for Run 2 Hybrid + MetadataResolver
│   ├── run2_metadata_hybrid_results.json # Machine-readable Run 2 vs Run 1 evaluation comparison
│   ├── run2_metadata_report.md     # Markdown evaluation report for Run 2 metadata resolution
│   ├── run3a_precedence_audit.jsonl # Per-question audit records for Run 3A Precedence & Conflict Suppression
│   ├── run3a_precedence_hybrid_results.json # Machine-readable Run 3A vs Run 2 vs Run 1 evaluation comparison
│   ├── run3a_precedence_report.md  # Markdown evaluation report for Run 3A precedence & conflict suppression
│   ├── run3b_canonical_audit.jsonl # Per-question audit records for Run 3B Canonical Entity Resolution
│   ├── run3b_canonical_hybrid_results.json # Machine-readable Run 3B vs Run 3A vs Run 2 vs Run 1 evaluation comparison
│   ├── run3b_canonical_report.md   # Markdown evaluation report for Run 3B canonical entity resolution
│   ├── run3b_resolution_audit.jsonl # Resolution candidate ledger with top/second scores and acceptance status
│   ├── run3b_canonical_audit_corrected.jsonl # Corrected Run 3B audit ledger under channel-strict accounting
│   ├── run3b_canonical_hybrid_results_corrected.json # Corrected Run 3B metric summary under channel-strict accounting
│   ├── phase31c_oracle_audit.jsonl # Per-question audit records for Phase 31C Oracle Control evaluation
│   ├── phase31c_oracle_results.json # Machine-readable Phase 31C Oracle Control evaluation metrics
│   ├── phase31c_oracle_report.md   # Markdown evaluation report for Phase 31C Oracle Control
│   ├── phase31d_edge_case_report.md # Markdown evaluation report for Phase 31D Edge-Case Classifications
│   ├── phase32b_passage_hydration_audit.jsonl # Per-question audit records for Step 32B Multi-Hop Passage Hydration
│   ├── phase32b_passage_hydration_results.json # Machine-readable Step 32B benchmark results and gates
│   ├── phase32b_passage_hydration_report.md   # Markdown evaluation report for Step 32B
│   ├── phase32c_adaptive_hydration_audit.jsonl # Per-question audit records for Step 32C Adaptive Passage Hydration
│   ├── phase32c_adaptive_hydration_results.json # Machine-readable Step 32C benchmark results and preservation gates
│   ├── phase32c_adaptive_hydration_report.md   # Markdown evaluation report for Step 32C
│   ├── phase33_final_release_audit.jsonl # Per-question audit records for Phase 33 Final Release Benchmark
│   ├── phase33_final_release_results.json # Machine-readable Phase 33 Final Release Benchmark metrics
│   ├── phase33_final_release_report.md # Markdown evaluation report for Phase 33 Final Release Benchmark
│   ├── phase33d_repeatability_results.json # Machine-readable Phase 33D 3-Run Repeatability Study metrics
│   ├── phase33d_repeatability_report.md # Comprehensive Phase 33D 3-Run Stability & Repeatability Report
│   ├── phase33d_run3_audit.jsonl   # Per-question audit records for Phase 33D Run 3 fresh execution
│   ├── neo4j/                      # Neo4j persistent database data & plugins
│   └── postgres/                   # PostgreSQL/pgvector database storage
├── src/                            # Production source code
│   ├── __init__.py                 # Root package initializer
│   ├── api/                        # Phase 7 & 9: FastAPI service & Material 3 Web Interface
│   │   ├── __init__.py             # API package exports
│   │   ├── main.py                 # App factory, CORS, lifespan teardown, static mount
│   │   ├── routes.py               # Route handlers: /query, /health, /stats, /graph/subgraph
│   │   ├── schemas.py              # Pydantic request & response DTOs (including SubgraphResponse)
│   │   └── static/                 # Material 3 Zero-Node Web Application
│   │       ├── app.js              # ES6 client logic: query dispatch, graph rendering, telemetry
│   │       ├── index.html          # Semantic HTML5 layout with M3 navigation rail & split workspace
│   │       └── style.css           # Vanilla CSS implementing Google Material Design 3 tokens
│   ├── core/                       # Phase 0 & Phase 6: Foundations, config & caching
│   │   ├── __init__.py             # Core package exports
│   │   ├── cache.py                # Normalized query response LRU cache (SHA-256)
│   │   ├── config.py               # Pydantic Settings v2 singleton (get_settings)
│   │   └── logging.py              # Structured, handler-idempotent console logging
│   ├── eval/                       # Phase 8 & 23: Benchmarking & evaluation suite
│   │   ├── __init__.py             # Eval package exports (with lazy loading)
│   │   ├── benchmark_integrity.py  # Dataset SHA-256 fingerprinting & strict 50Q validation
│   │   ├── dataset.py              # 50-question stratified benchmark catalog
│   │   ├── evaluator_v2.py         # Decoupled 5-layer evaluator with negation & graph evidence
│   │   ├── models_v2.py            # Typed benchmark models with fact_evaluable & validation
│   │   ├── report.py               # Markdown table generator & README updater
│   │   ├── runner.py               # Comparative benchmark runner (fail-closed zero leakage)
│   │   └── text_norm.py            # Centralized Unicode NFKC & punctuation normalizer
│   ├── graph/                      # Phase 2 & Phase 4: Neo4j knowledge graph engine
│   │   ├── __init__.py             # Graph package exports
│   │   ├── canonical_resolver.py   # 6-tier canonical document & entity resolver with ambiguity gate (ADR 053)
│   │   ├── community.py            # Pure-Python LPA graph clustering & corpus summaries
│   │   ├── extractor.py            # Schema-validated fact extraction with retry loop
│   │   ├── models.py               # Pydantic ontology entities & relationship models
│   │   ├── query_engine.py         # Parameterized graph query engine & statement formatter
│   │   ├── resolver.py             # Multi-stage entity resolution (lexical + Jaccard + cosine)
│   │   ├── templates.py            # Parameterized Cypher template catalog (zero text-to-Cypher)
│   │   └── writer.py               # Idempotent MERGE writer with uniqueness constraints
│   ├── ingestion/                  # Phase 1: Corpus acquisition & chunking
│   │   ├── __init__.py             # Ingestion package exports
│   │   ├── chunker.py              # Recursive boundary chunker with SHA-256 digests
│   │   ├── collector.py            # Polite arXiv API client (>=3s throttle) & Semantic Scholar
│   │   ├── models.py               # Author, Paper, and DocumentChunk data models
│   │   └── orchestrator.py         # Asynchronous multi-stage corpus ingestion manager
│   ├── memory/                     # Phase 5: Session dialogue memory
│   │   ├── __init__.py             # Memory package exports
│   │   └── session.py              # Sliding-window buffer (k=3) & pronoun coreference
│   ├── router/                     # Phase 5: Query classification & coordination
│   │   ├── __init__.py             # Router package exports
│   │   ├── classifier.py           # Tri-state intent classifier with <0.70 escalation
│   │   ├── coordinator.py          # Central retrieval coordinator with dynamic top-k, cosine filtering, and Step 32A graph passage hydration (ADRs 033, 060)
│   │   ├── metadata_resolver.py    # Dedicated provenance-aware catalog metadata resolver (ADR 051)
│   │   ├── models.py               # RouteDecision, RoutingResult, and RetrievalContext with Phase 32 & ADR 070 telemetry fields
│   │   └── refiner.py              # Bounded LangGraph evidence refinement module on detected gaps (ADR 070)
│   └── vector/                     # Phase 3: pgvector dense vector store
│       ├── __init__.py             # Vector package exports
│       ├── indexer.py              # Dense embeddings generator, pgvector upsert store, and indexed get_chunks_by_ids (Step 32A)
│       ├── models.py               # VectorChunkRecord and VectorSearchResult models
│       ├── schema.py               # SQLAlchemy async ORM DocumentChunkModel & schema init
│       └── tuning.py               # HNSW ef_search tuner against flat scan ground truth
├── evalkit/                        # Unified authoritative evaluation framework (14 metrics, caching, regression, CLI)
│   ├── evalkit/                    # Core evaluation package
│   │   ├── adapters/               # Target system adapters (e.g. StaticAdapter)
│   │   ├── contracts/              # Adapter & run contracts (AdapterResponse, MetricResult)
│   │   ├── core/                   # Runner, report generation, dataset loader, config, cache, regression, run_store
│   │   ├── evaluators/             # Retrieval (precision, recall, MRR, nDCG), RAG, NLP, Graph
│   │   └── judges/                 # LiteLLM judge with structured JSON parsing, backoff, and cache fingerprinting
│   ├── evalharness/                # Internal backward-compatibility forwarding shims pointing to evalkit
│   └── tests/                      # Full evaluation test suite (244 tests)
├── tests/                          # Automated verification test suite (156 tests, 100% offline)
│   ├── test_api.py                 # FastAPI endpoint tests (root, health, stats, /query, /graph/communities)
│   ├── test_community.py           # LPA clustering, summary record, and caching tests
│   ├── test_config.py              # Settings validation and logger tests
│   ├── test_eval.py                # Dataset stratification, runner, and report tests
│   ├── test_eval_v2.py             # 9 integrity regression properties (paraphrase, hyphens, abstention)
│   ├── test_evalkit_adapter.py     # Evalkit adapter & dataset exporter verification tests
│   ├── test_evidence_refinement.py # Bounded LangGraph refinement unit & integration tests (ADR 070)
│   ├── test_full_evaluation.py     # Multi-track evaluation, stratification, metric filter & aggregation tests
│   ├── test_graph.py               # Fact extraction, resolution, and cache tests
│   ├── test_ingestion.py           # Paper model, chunking determinism, collector & incremental tests
│   ├── test_metadata_resolver.py   # Dedicated MetadataResolver unit tests & coordinator integration (ADR 051)
│   ├── test_query_engine.py        # Cypher templates, entity lookup, and formatting tests
│   ├── test_router.py              # Sliding window, coreference, classifier, and coordinator tests
│   ├── test_synthesis.py           # Context assembly, citation validation, cache, and retries
│   ├── test_text_norm.py           # Unicode NFKC, hyphen variants, apostrophes, and whitespace tests
│   └── test_vector.py              # Schema, deterministic unit vectors, and similarity scoring
├── data/                           # Evaluation reports, benchmark datasets & bundle
│   ├── evalkit_vs_ragas_comparison.md  # Side-by-side Evalkit vs Ragas calibration report
│   ├── evalkit_vs_ragas_comparison.json# Raw per-question scores for Evalkit & Ragas
│   ├── phase30b_path_formatting_report.md # Phase 30B concise relational formatting evaluation report
│   ├── phase30b_path_formatting_results.json # Phase 30B raw 50Q results & comparative metrics
│   ├── phase30b_path_formatting_audit.jsonl # Phase 30B exact context & provenance audit ledger
│   ├── phase30_path_formatting_report.md # Phase 30 relational path formatting evaluation report
│   ├── phase30_path_formatting_results.json # Phase 30 raw 50Q results & comparative metrics
│   ├── phase30_path_formatting_audit.jsonl # Phase 30 per-question provenance & evaluation audit
│   ├── evidence_refinement_benchmark_results.json # 32B Champion + Bounded Refinement metrics (Run 1)
│   ├── evidence_refinement_benchmark_audit.jsonl # 32B + Refinement per-question context audit (Run 1)
│   ├── evidence_refinement_benchmark_report.md # 32B + Refinement comparative evaluation report
│   ├── hybrid_repeatability_results.json # 3-Run repeatability aggregated metrics & stability analysis
│   ├── hybrid_repeatability_report.md    # 3-Run repeatability markdown report & gate verdicts
│   ├── hybrid_repeatability_run2_audit.jsonl # Run 2 fresh 50Q rerun audit log
│   ├── hybrid_repeatability_run3_audit.jsonl # Run 3 fresh 50Q rerun audit log
│   ├── langgraph_benchmark_results.json # Standalone LangGraph 9-node benchmark metrics
│   ├── langgraph_benchmark_audit.jsonl  # Standalone LangGraph per-question audit log
│   ├── langgraph_benchmark_report.md   # Standalone LangGraph evaluation report
│   ├── run3b_canonical_report.md   # Run 3B canonical entity resolution evaluation report
│   ├── run3b_canonical_results.json# Run 3B raw 50Q results & comparative metrics
│   ├── run3b_resolution_audit.jsonl# Run 3B canonical resolver resolution ledger
│   ├── run3a_precedence_report.md  # Run 3A precedence & suppression evaluation report
│   ├── run3a_precedence_results.json # Run 3A raw 50Q results & comparative metrics
│   ├── run2_metadata_ablation_results.json # Run 2 metadata ablation raw scores
│   ├── full_evaluation/            # Full 50-question multi-track benchmark evaluation outputs
│   │   ├── full_eval_report.md     # Stratified markdown report with score legitimacy audit
│   │   ├── full_eval_results.json  # Raw per-question scores across all tracks
│   │   └── spot_check_samples.md   # Sampled QA pairs for manual verification
│   └── test_evaluation_bundle/     # Master prompt-ready bundle for Claude/GPT analysis
│       ├── MASTER_TEST_AND_EVAL_REPORT.md  # Comprehensive testing & evaluation report
│       ├── EVALUATION_AUDIT_PROOF.md       # Audit and mathematical/empirical score legitimacy proof
│       ├── benchmark_results_50q.json      # 50-question comparative benchmark run
│       ├── evalkit_results_10q.json        # External evalkit multi-track evaluation output
│       ├── evalkit_report_10q.md           # Evalkit formatted report per example
│       ├── live_eval_run_10q/              # Live 10-question evaluation report with Nemotron-3 judge
│       ├── live_eval_run_2hop/             # Live 2-hop evaluation report with Nemotron-3 judge
│       ├── live_eval_run_10q_optimized/    # Optimized 10-question run with ADR 033 dynamic top-k
│       ├── benchmark_validation/           # Statistical validation, bootstrap CIs & dual-judge report
│       └── pytest_test_suite_log.txt       # Raw pytest 83-test execution log
├── scripts/                        # Standalone utility & export scripts
│   ├── compare_evalkit_vs_ragas.py # Dual-evaluator driver comparing Evalkit vs Ragas on GraphRAG
│   ├── compile_results_bundle.py   # Compiles evaluation reports, datasets, audit logs & specs into ZIP
│   ├── export_evalkit_dataset.py   # Exports canonical benchmark dataset to evalkit JSONL
│   ├── generate_benchmark_v2_dataset.py # Generates authoritative fact ground truth dataset
│   ├── run_benchmark_v2.py         # Full Evaluation V2 benchmark driver
│   ├── run_canonical_ablation_run3b.py # Run 3B canonical entity resolution benchmark runner
│   ├── run_full_evaluation.py      # Multi-track benchmark runner with metric auditing & spot checks
│   ├── run_path_formatting_phase30.py # Phase 30 relational traversal path benchmark runner
│   ├── run_path_formatting_phase30b.py # Phase 30B concise relational formatting benchmark runner
│   ├── recompute_run3b_corrected_accounting.py # Recalculates Run 3B metrics under channel-strict accounting
│   ├── run_phase31c_oracle_control.py # Phase 31C Oracle Control evaluation driver on 16 failed questions
│   ├── run_phase33_release_benchmark.py # Phase 33 final re-benchmark & release champion runner
│   ├── langgraph_evidence_refinement.py # Hybrid 32B Champion + Bounded 1-Pass LangGraph Evidence Refinement
│   ├── run_evidence_refinement_benchmark.py # Isolated benchmark driver for 32B Champion + Refinement
│   ├── run_hybrid_repeatability_study.py # 3-Run repeatability study runner across Runs 1-3
│   ├── validate_benchmark.py       # Independent score validator with bootstrap CIs & dual-judge cross-check
│   └── verify_basic_metrics.py     # Standalone validation verifying all 10 basic metrics + GraphRAG
├── _local_archive/                 # Local directory for unpushed experimental scripts & audit logs (gitignored)
│   ├── README.md                   # Archive directory inventory & exclusion rationale
│   ├── scripts/                    # Exploratory prototypes (langgraph_graphrag, package_codebase, etc.)
│   ├── data/                       # Local raw benchmark dumps (.json), per-query audit ledgers (.jsonl)
│   └── legacy/                     # Pre-rename evalharness package copy & test result notes
├── eval_adapter.py                 # Standalone BaseAdapter wrapping GraphRAG for evalkit
├── evalkit_config.yaml             # Multi-track evalkit configuration (rag + text_similarity)
├── run_evalkit.py                  # Standalone evalkit evaluation runner generating reports
├── docker-compose.yml              # Local container definitions for Neo4j Community & PostgreSQL
├── pyproject.toml                  # Python package configuration, dependencies, and pytest options
├── requirements.txt                # Pinned production & development dependencies
└── README.md                       # Repository landing page, benchmark table, and quickstart
```

---

## 2. Detailed Per-Module Inventory

### 2.1 Core Foundations (`src/core/`)

#### [`src/core/config.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/config.py)
- **Role**: Single source of truth for all runtime configuration parameters and environment variables.
- **Key Symbols**: [`Settings`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/config.py#L28), [`get_settings`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/config.py#L173).
- **Inputs**: `.env` file and system environment variables.
- **Outputs**: Validated `Settings` singleton with LRU caching.
- **Key Settings**: `llm_base_url`, `llm_api_key`, `neo4j_uri`, `postgres_async_uri`, `arxiv_delay_seconds`.

#### [`src/core/logging.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/logging.py)
- **Role**: Standardized console logging with handler idempotency.
- **Key Symbols**: [`setup_logger`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/logging.py#L26).
- **Inputs**: Module name string and logging level.
- **Outputs**: Configured `logging.Logger` instance.

#### [`src/core/cache.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/cache.py)
- **Role**: Thread-safe in-memory LRU cache for query responses.
- **Key Symbols**: [`QueryResponseCache`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/cache.py#L42), [`CacheStats`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/core/cache.py#L22).
- **Inputs**: Raw query string and synthesized answer.
- **Outputs**: Cached answer objects on cache hits; hit/miss statistics.
- **Key Invariant**: Normalizes query (lowercase, trim, collapse whitespace, strip punctuation) before computing the SHA-256 key.

---

### 2.2 Ingestion & Chunking (`src/ingestion/`)

#### [`src/ingestion/models.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/models.py)
- **Role**: Document and ingestion contract models.
- **Key Symbols**: [`Author`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/models.py#L22), [`Paper`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/models.py#L32), [`DocumentChunk`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/models.py#L52).

#### [`src/ingestion/collector.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/collector.py)
- **Role**: Polite academic literature harvester.
- **Key Symbols**: [`PaperCollector`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/collector.py#L48).
- **Inputs**: Search query topic, max results limit.
- **Outputs**: List of structured `Paper` objects.
- **Invariants**: Enforces strict $\ge 3.0$s inter-request rate limiting; includes Windows SSL `curl.exe` transport fallback.

#### [`src/ingestion/chunker.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/chunker.py)
- **Role**: Recursive natural boundary document segmenter.
- **Key Symbols**: [`DocumentChunker`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/chunker.py#L43).
- **Inputs**: `Paper` model or raw text with section headers.
- **Outputs**: List of `DocumentChunk` instances with deterministic SHA-256 chunk IDs.

#### [`src/ingestion/orchestrator.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/orchestrator.py)
- **Role**: Asynchronous multi-stage corpus ingestion manager.
- **Key Symbols**: [`IngestionOrchestrator`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/orchestrator.py#L35), [`get_ingestion_orchestrator`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/ingestion/orchestrator.py#L220).
- **Inputs**: `IngestRequest` parameters (harvest mode vs existing corpus, query, limits, toggles).
- **Outputs**: Coordinated execution across collector, chunker, vector store, and Neo4j graph writer, with atomic progress telemetry.

---

### 2.3 Knowledge Graph Engine (`src/graph/`)

#### [`src/graph/models.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/models.py)
- **Role**: Formal Pydantic representations of ontology entities and relationships.
- **Key Symbols**: [`EntityType`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/models.py#L26), [`RelationType`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/models.py#L40), [`ExtractedFact`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/models.py#L56), [`ResolvedEntity`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/models.py#L76).

#### [`src/graph/extractor.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/extractor.py)
- **Role**: LLM-driven ontology-constrained knowledge graph extraction.
- **Key Symbols**: [`GraphExtractor`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/extractor.py#L76).
- **Inputs**: List of `DocumentChunk` objects.
- **Outputs**: List of schema-validated `ExtractedFact` objects.
- **Invariants**: Caches extractions by chunk hash in `data/cache/extraction_cache.json`; retries up to 3 times on validation failure.

#### [`src/graph/resolver.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/resolver.py)
- **Role**: Multi-stage deduplication and alias linkage.
- **Key Symbols**: [`EntityResolver`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/resolver.py#L45).
- **Inputs**: Raw entity strings and extracted facts.
- **Outputs**: Canonical entities with accumulated aliases.
- **Invariants**: Employs NFKD normalization, token Jaccard similarity, and cosine similarity $\ge 0.88$.

#### [`src/graph/canonical_resolver.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/canonical_resolver.py)
- **Role**: Deterministic 6-tier entity and document resolution ladder with ambiguity gates (ADR 053).
- **Key Symbols**: [`CanonicalEntityResolver`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/canonical_resolver.py#L111), [`ResolutionResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/canonical_resolver.py#L96), [`CandidateEvaluation`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/canonical_resolver.py#L86).
- **Inputs**: Surface mention string or router-detected entity name, document corpus catalog, registered Neo4j nodes.
- **Outputs**: `ResolutionResult` containing authoritative `canonical_id`, `canonical_name`, `entity_type`, `top_score`, `second_score`, and acceptance flag.
- **Invariants**: Executes 6 tiers: Canonical ID -> Normalized arXiv ID -> Exact Normalized Title -> Curated Alias -> Token Jaccard ($\ge 0.85$) -> Ambiguity Gate (`top < 0.85` or `top - second < 0.15` rejects). Pre-execution gate skips Cypher on rejected targets. Records full candidate set in `resolution_audit_log`.

#### [`src/graph/writer.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/writer.py)
- **Role**: Idempotent Cypher write pipeline into Neo4j.
- **Key Symbols**: [`Neo4jWriter`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/writer.py#L43).
- **Inputs**: Resolved `ExtractedFact` records.
- **Outputs**: Populated Neo4j property graph with uniqueness constraints and indexed `source_chunk_id` attributes.

#### [`src/graph/templates.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/templates.py)
- **Role**: Parameterized Cypher query catalog.
- **Key Symbols**: [`QueryTemplateType`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/templates.py#L32), [`CypherTemplate`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/templates.py#L48), [`CYPHER_TEMPLATES`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/templates.py#L60).
- **Invariants**: Pre-compiled queries for 1-hop, 2-hop, and 3-hop traversals; every edge projects `source_chunk_id`.

#### [`src/graph/query_engine.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/query_engine.py)
- **Role**: Injection-safe query translation, execution, canonical resolution gating, and explicit relational path statement formatting (Phase 30 / ADR 054).
- **Key Symbols**: [`GraphQueryEngine`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/query_engine.py#L64), [`GraphQueryResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/query_engine.py#L46).
- **Inputs**: Natural language query string, pre-identified entities.
- **Outputs**: Formatted explicit relational path statements (`Path: A --[:REL]--> B. Therefore, the retrieved evidence establishes: ... [chunk: ...]`).
- **Invariants**: Strict ambiguity gating via `CanonicalEntityResolver`; zero inferred edges (all paths project actual Neo4j query rows); preserves `[chunk: ...]` citations on all steps.

#### [`src/graph/community.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/community.py)
- **Role**: Pure-Python Label Propagation Algorithm (LPA) clustering and hierarchical corpus-level summary synthesis.
- **Key Symbols**: [`GraphCommunityDetector`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/community.py#L48), [`CommunitySummaryRecord`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/community.py#L38), [`CommunityDetectionResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/graph/community.py#L48).
- **Inputs**: Neo4j graph relationships and natural language queries.
- **Outputs**: Discovered community clusters, degree-centrality ranked entities, and synthesized thematic summaries.
- **Invariants**: $O(V + E)$ pure-Python LPA with deterministic random seed; in-memory TTL caching ($300$s).

---

### 2.4 Vector Store & pgvector (`src/vector/`)

#### [`src/vector/schema.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/schema.py)
- **Role**: SQLAlchemy async ORM table definition for PostgreSQL.
- **Key Symbols**: [`DocumentChunkModel`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/schema.py#L34), [`init_vector_db`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/schema.py#L64).

#### [`src/vector/models.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/models.py)
- **Role**: Pydantic data transfer objects for vector operations.
- **Key Symbols**: [`VectorChunkRecord`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/models.py#L22), [`VectorSearchResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/models.py#L38).

#### [`src/vector/indexer.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/indexer.py)
- **Role**: Dense embedding generation and pgvector similarity search.
- **Key Symbols**: [`EmbeddingGenerator`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/indexer.py#L53), [`VectorStore`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/indexer.py#L125).
- **Inputs**: `DocumentChunk` instances, query strings, `top_k`.
- **Outputs**: Top-k `VectorSearchResult` records ordered by cosine similarity.
- **Invariants**: Deterministic unit vector mock fallback when offline; batched embeddings ($N=32$); idempotent upsert (`ON CONFLICT DO UPDATE`).

#### [`src/vector/tuning.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/tuning.py)
- **Role**: HNSW index configuration and `ef_search` recall benchmark script.
- **Key Symbols**: [`HNSWTuner`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/tuning.py#L44), [`TuningResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/vector/tuning.py#L29).

---

### 2.5 Dialogue Memory & Router (`src/memory/`, `src/router/`)

#### [`src/memory/session.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/memory/session.py)
- **Role**: Sliding-window dialogue buffer ($k=3$ turn pairs) and pronoun coreference resolution.
- **Key Symbols**: [`SessionMemory`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/memory/session.py#L59), [`SessionTurn`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/memory/session.py#L42).
- **Inputs**: Multi-turn user and assistant messages.
- **Outputs**: Coreference-resolved, self-contained questions.

#### [`src/router/models.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/models.py)
- **Role**: Enums and data structures for retrieval decisions and hydration telemetry.
- **Key Symbols**: [`RouteDecision`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/models.py#L29), [`RoutingResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/models.py#L38), [`RetrievalContext`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/models.py#L77) (with `hydration_budget` and `hydration_reason`).

#### [`src/router/classifier.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/classifier.py)
- **Role**: Tri-state query intent classifier with confidence escalation guardrail.
- **Key Symbols**: [`RouteClassifier`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/classifier.py#L93).
- **Inputs**: User query string.
- **Outputs**: `RoutingResult` (`graph`, `vector`, or `both`).
- **Invariants**: If confidence is $< 0.70$, automatically escalates to `both`; includes deterministic regex heuristic fallback for offline testing.

#### [`src/router/coordinator.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/coordinator.py)
- **Role**: Central coordinator managing dialogue memory, intent routing, multi-modal database retrieval, Step 32A graph passage hydration, and Step 3f conditional LangGraph evidence refinement.
- **Key Symbols**: [`RetrievalCoordinator`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/coordinator.py#L123), [`compute_adaptive_hydration_budget`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/coordinator.py#L58), [`MULTIHOP_CYPHER_TEMPLATES`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/coordinator.py#L50).
- **Inputs**: Query string, optional session ID, `top_k`, optional route override.
- **Outputs**: Unified `RetrievalContext` containing graph facts, vector text chunks, hydrated passages, citation IDs, and refinement telemetry.

#### [`src/router/refiner.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/refiner.py)
- **Role**: Bounded single-pass LangGraph evidence refinement module (ADR 070). Activated conditionally when heuristic gap detector identifies missing ontology entities or catalog document IDs.
- **Key Symbols**: [`EvidenceRefiner`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/refiner.py#L60), [`RefinementState`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/router/refiner.py#L42).
- **Inputs**: Query string, initial graph facts, initial vector search chunks.
- **Outputs**: Refined graph facts (<= 3), refined vector chunks (<= 2), gap telemetry, and timing breakdowns.
- **Invariants**: 100% deterministic heuristic gap detector (<1ms, zero-LLM overhead); linear 3-node StateGraph (isolate_gap -> targeted_retrieval -> merge_evidence); all refined chunk IDs registered in `cited_chunk_ids`; try/except fallback to unrefined context on external model/DB failure.

---

### 2.6 Synthesis & Citation Validation (`src/synthesis/`)

#### [`src/synthesis/validator.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/validator.py)
- **Role**: Deterministic AST/regex citation verification hard gate.
- **Key Symbols**: [`CitationValidator`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/validator.py#L52), [`CitationValidationResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/validator.py#L31).
- **Inputs**: Generated answer string and allowed retrieved `source_chunk_id` list.
- **Outputs**: `CitationValidationResult` flagging validity, valid IDs, and hallucinated IDs.
- **Invariants**: 100% rejection on unretrieved citation IDs.

#### [`src/synthesis/synthesizer.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/synthesizer.py)
- **Role**: Context assembler (`[graph]` / `[retrieved]`), LLM synthesis orchestrator, and regeneration retry loop.
- **Key Symbols**: [`AnswerSynthesizer`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/synthesizer.py#L71), [`SynthesizedAnswer`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/synthesis/synthesizer.py#L46).
- **Inputs**: `RetrievalContext`.
- **Outputs**: Validated, grounded `SynthesizedAnswer`.
- **Invariants**: Retries up to 2 times with targeted error feedback on hallucination; deterministic offline synthesis fallback.

---

### 2.7 Production REST API (`src/api/`)

#### [`src/api/schemas.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py)
- **Role**: Inbound request and outbound response DTOs.
- **Key Symbols**: [`QueryRequest`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L25), [`QueryResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L48), [`HealthResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L82), [`StatsResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L96), [`SubgraphResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L125), [`IngestRequest`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L150), [`IngestStatusResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/schemas.py#L170).

#### [`src/api/routes.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py)
- **Role**: FastAPI route handlers for `/query`, `/health`, `/stats`, `/graph/subgraph`, `/chunks/{id}`, `/ingest`, and `/ingest/status`.
- **Key Symbols**: [`router`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L29), [`query_endpoint`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L52), [`health_endpoint`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L112), [`stats_endpoint`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L151), [`ingest_endpoint`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L220), [`ingest_status_endpoint`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/routes.py#L245).

#### [`src/api/main.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/main.py)
- **Role**: Application entry point, CORS middleware, and ASGI lifespan resource teardown.
- **Key Symbols**: [`create_application`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/main.py#L58), [`lifespan`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/main.py#L29), [`app`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/api/main.py#L98).

---

### 2.8 Benchmarking Suite (`src/eval/`)

#### [`src/eval/text_norm.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/text_norm.py)
- **Role**: Shared canonical Unicode NFKC, lowercase, apostrophe, hyphen variant (`‐ ‒ – — ― − -` -> `-`), and whitespace normalizer.
- **Key Symbols**: [`normalize_text`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/text_norm.py#L42).

#### [`src/eval/models_v2.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/models_v2.py)
- **Role**: Authoritative data contracts for Evaluation V2 (fact-level ground truth and per-question audit records).
- **Key Symbols**: [`BenchmarkQuestionV2`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/models_v2.py#L52), [`RequiredFact`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/models_v2.py#L27), [`QuestionAuditRecord`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/models_v2.py#L75).

#### [`src/eval/evaluator_v2.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/evaluator_v2.py)
- **Role**: Decoupled 5-layer evaluation engine (Retrieval, Factual Correctness, Context Groundedness, Answerability, Efficiency) with 4 mandatory safeguards (refusal never zeroes satisfied facts, zero-leakage per-fact semantic judge fallback, contradiction precedence, and `fact_verdicts` evidence trail).
- **Key Symbols**: [`EvaluatorV2`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/evaluator_v2.py#L138), [`compute_token_f1`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/evaluator_v2.py#L74), [`compute_lexical_chunk_overlap`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/evaluator_v2.py#L96), [`is_refusal`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/evaluator_v2.py#L58).

#### [`src/eval/dataset.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/dataset.py)
- **Role**: 50-question stratified benchmark dataset spanning 5 complexity tiers.
- **Key Symbols**: [`EvalHopType`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/dataset.py#L22), [`EvalQuestion`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/dataset.py#L31), [`BenchmarkDataset`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/dataset.py#L48), [`get_canonical_evaluation_dataset`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/dataset.py#L61).

#### [`src/eval/runner.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/runner.py)
- **Role**: Side-by-side evaluation runner comparing Hybrid GraphRAG vs. Plain Vector Baseline (purged of synthetic question-ID overrides and `matches > 0` shortcuts).
- **Key Symbols**: [`BenchmarkRunner`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/runner.py#L74), [`EvalMetricRecord`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/runner.py#L34), [`ComparativeBenchmarkResult`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/runner.py#L55).

#### [`src/eval/report.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/report.py)
- **Role**: Markdown table rendering, JSON report persistence, and README updater.
- **Key Symbols**: [`BenchmarkReporter`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/src/eval/report.py#L25).

---

### 2.9 Standalone Evaluation & Utility Scripts (`scripts/`)

#### [`scripts/run_benchmark_v2.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_benchmark_v2.py)
- **Role**: Driver executing the Evaluation V2 benchmark comparing Hybrid GraphRAG against Plain Vector RAG over authoritative fact-level ground truth.
- **Outputs**: `data/benchmark_results_50q_v2.json`, `data/benchmark_audit_records_v2.jsonl`, `data/benchmark_audit_table_v2.md`, `data/benchmark_comparison_v1_vs_v2.json`.

#### [`scripts/generate_benchmark_v2_dataset.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/generate_benchmark_v2_dataset.py)
- **Role**: Compiles authoritative fact ground truth dataset `data/benchmark_v2_dataset.jsonl` with structured required facts and weights.

#### [`scripts/run_full_evaluation.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_full_evaluation.py)
- **Role**: Standalone multi-track evaluation harness executing all 50 canonical benchmark questions via `evalkit`.
- **Key Symbols**: `run_all_tracks`, `aggregate_results`, `generate_markdown_report`, `generate_json_report`, `generate_spot_checks`.
- **Inputs**: `data/evalkit_dataset.jsonl`, `eval_adapter.py:GraphRAGAdapter`.
- **Outputs**: `full_eval_results.json`, `full_eval_report.md`, `spot_check_samples.md`.

#### [`scripts/verify_basic_metrics.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/verify_basic_metrics.py)
- **Role**: Standalone metric validation runner verifying all 10 core metrics (context precision, context recall, MRR, nDCG, faithfulness, answer relevancy, BLEU, ROUGE-L, BERTScore, answer correctness, hallucination rate, latency, cost) across retrieval, generation, similarity, and runner aggregation.
- **Key Symbols**: `test_retrieval_metrics`, `test_rag_metrics`, `test_text_similarity_metrics`, `test_runner_aggregation_all_10_metrics`.

#### [`scripts/compare_evalkit_ragas_deepeval.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/compare_evalkit_ragas_deepeval.py)
- **Role**: Multi-framework comparative evaluation driver evaluating identical frozen GraphRAG output snapshots (`data/eval_framework_snapshot.jsonl`) across Evalkit, Ragas, and DeepEval.
- **Outputs**: `data/eval_framework_comparison_3way.md`, `data/eval_framework_comparison_3way.json`.

#### [`scripts/run_abcd_ablation.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_abcd_ablation.py)
- **Role**: 4-Way Ablation Benchmark Runner executing Mode A (Vector), Mode B (Graph), Mode C (Hybrid), and Mode D (Oracle) with extended telemetry and Types A–F failure taxonomy triage.
- **Outputs**: `data/abcd_ablation_results.json`, `data/abcd_ablation_audit.jsonl`, `data/abcd_ablation_report.md`.

#### [`scripts/run_phase33_release_benchmark.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_phase33_release_benchmark.py)
- **Role**: Driver executing Phase 33 Final Release Benchmark on the frozen Step 32B champion configuration (`enable_graph_passage_hydration=True`, `max_graph_hydrated_passages=3`, `enable_adaptive_hydration=False`) across all 50 questions, evaluating Required Quality Criteria and the accepted context-efficiency trade-off.
- **Outputs**: `data/phase33_final_release_results.json`, `data/phase33_final_release_audit.jsonl`, `data/phase33_final_release_report.md`.

#### [`scripts/run_phase33d_repeatability_study.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_phase33d_repeatability_study.py)
- **Role**: Repeatability study runner executing 3 independent frozen 50Q runs (Run 1: 32B peak, Run 2: P33 rerun 1, Run 3: P33 rerun 2 fresh) to quantify downstream NIM generator variance, per-question stability matrix, and stage-decomposed latencies.
- **Outputs**: `data/phase33d_repeatability_results.json`, `data/phase33d_repeatability_report.md`, `data/phase33d_run3_audit.jsonl`.

#### [`run_evalkit.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/run_evalkit.py) & [`evalkit_config.yaml`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalkit_config.yaml)
- **Role**: Authoritative Enterprise Benchmark Runner. Orchestrates end-to-end multi-track evaluation across 4 tracks (`rag`, `retrieval`, `graph`, `text_similarity`) over `data/benchmark_v2_dataset.jsonl` using `evalharness` engine, LiteLLM judge with NVIDIA NIM auto-credentials, and persistent caching.
- **Key Symbols**: [`run_evaluation`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/run_evalkit.py), [`main`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/run_evalkit.py).
- **Inputs**: `evalkit_config.yaml`, `data/benchmark_v2_dataset.jsonl`, `eval_adapter:GraphRAGAdapter`.
- **Outputs**: `data/evalkit_report.md`, `data/evalkit_results.json`.

---

### 2.10 Unified Evaluation Harness (`evalharness/`)

#### [`evalharness/contracts/adapter.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/contracts/adapter.py)
- **Role**: Data contracts defining `BaseAdapter` interface and `AdapterResponse` dataclass.
- **Key Symbols**: [`AdapterResponse`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/contracts/adapter.py), [`BaseAdapter`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/contracts/adapter.py).

#### [`evalharness/judges/litellm_judge.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/judges/litellm_judge.py)
- **Role**: LLM-as-a-judge scorer using LiteLLM with structured JSON parsing (`response_format: json_object`), fallback retry, code fence stripping, and range validation ($[0.0, 1.0]$).
- **Key Symbols**: [`LiteLLMJudge`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/judges/litellm_judge.py).

#### [`evalharness/evaluators/retrieval.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/evaluators/retrieval.py)
- **Role**: Evaluates retrieval performance over retrieved chunk IDs against gold targets.
- **Metrics**: `context_precision`, `context_recall`, `mrr`, `ndcg_at_k` (with position discounting).

#### [`evalharness/evaluators/rag.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/evaluators/rag.py)
- **Role**: LLM-judge evaluated generation metrics measuring context groundedness, relevance, and correctness.
- **Metrics**: `faithfulness`, `answer_relevancy`, `context_recall`, `answer_correctness`, `hallucination_rate`.

#### [`evalharness/evaluators/graph.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/evaluators/graph.py)
- **Role**: Dedicated GraphRAG dimension evaluator covering Indexing, Search, and Generation layers.
- **Metrics**: `graph_utilization_rate` (traversal efficiency), `community_coherence` (cluster summary fidelity), `global_diversity` (thematic breadth & non-repetition on global queries), `entity_relation_coverage` (triplet and entity extraction recall).

#### [`evalharness/evaluators/text_similarity.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/evaluators/text_similarity.py)
- **Role**: Traditional lexical and embedding similarity against reference answers.
- **Metrics**: `bleu_score`, `rouge_l_f1`, `bert_score_f1` (DistilBERT with memory-safe fallback).

#### [`evalharness/core/runner.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/core/runner.py)
- **Role**: Evaluation orchestrator executing adapters against datasets, recording latency and cost, and dispatching to evaluators.
- **Key Symbols**: [`Runner`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/core/runner.py).

#### [`evalharness/cache.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/cache.py), [`regression.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/regression.py), [`run_store.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalharness/evalharness/run_store.py)
- **Role**: Enterprise evaluation infrastructure providing thread-safe file caching, per-example regression detection, persistent run storage, and historical run diffing.

---

### 2.11 Candidate Architecture & Evaluation Scripts (`scripts/`)

#### [`scripts/langgraph_evidence_refinement.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_evidence_refinement.py)
- **Role**: Candidate Hybrid GraphRAG Architecture (Phase 34, ADR 068, ADR 069). Preserves the fast Phase 32B `RetrievalCoordinator` as the primary engine; executes a selective, bounded 1-pass LangGraph StateGraph (`isolate_gap_node` → `targeted_retrieval_node` → `merge_evidence_node`) only when an evidence gap is detected.
- **Key Symbols**: [`ChampionWithLangGraphRefinement`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_evidence_refinement.py), [`RefinementState`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_evidence_refinement.py).
- **Inputs**: Natural language query, optional session ID, `use_cache` flag.
- **Outputs**: Dictionary containing `answer`, `cited_chunk_ids`, `is_valid`, `refinement_activated`, `missing_entities`, `missing_doc_ids`, `retrieval_context`, `assembled_context`, `latencies`.

#### [`scripts/run_hybrid_repeatability_study.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/run_hybrid_repeatability_study.py)
- **Role**: Automated 3-run repeatability benchmark runner evaluating candidate hybrid GraphRAG across the canonical 50-question benchmark with complete cache isolation (`use_cache=False`).
- **Outputs**: `data/hybrid_repeatability_results.json`, `data/hybrid_repeatability_report.md`, `data/hybrid_repeatability_run2_audit.jsonl`, `data/hybrid_repeatability_run3_audit.jsonl`.

#### [`scripts/langgraph_graphrag.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_graphrag.py)
- **Role**: Standalone 9-node LangGraph StateGraph orchestrator with agentic citation self-correction loop (Phase 34, ADR 067).
- **Key Symbols**: [`LangGraphGraphRAG`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_graphrag.py).

#### [`scripts/langgraph_adapter.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/langgraph_adapter.py)
- **Role**: Adapter connecting LangGraph GraphRAG models to `evalkit` evaluation contracts.

#### [`scripts/test_langgraph_smoke.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/test_langgraph_smoke.py)
- **Role**: Isolated smoke test verifying the compiled LangGraph StateGraph executes all nodes and edges cleanly.

---

## 3. Test Suite Mapping

Every core production module, standalone script, and evaluation harness is paired with a dedicated test suite:

### 3.1 Core Repository Tests (`tests/`)

| Test Module | Target Tested Components | Tests Count | Status |
|---|---|---|---|
| [`test_config.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_config.py) | `Settings`, `get_settings`, `setup_logger` | 2 | PASSED |
| [`test_text_norm.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_text_norm.py) | Shared Unicode normalizer (`normalize_text`), hyphen variants, apostrophes, NFKC | 4 | PASSED |
| [`test_ingestion.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_ingestion.py) | `Paper`, `DocumentChunker`, `PaperCollector`, incremental hashing | 4 | PASSED |
| [`test_graph.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_graph.py) | `ExtractedFact`, `EntityResolver`, `GraphExtractor` cache | 5 | PASSED |
| [`test_vector.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_vector.py) | `DocumentChunkModel`, `VectorStore`, `EmbeddingGenerator` | 4 | PASSED |
| [`test_query_engine.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_query_engine.py) | `CYPHER_TEMPLATES`, `GraphQueryEngine` statement format | 4 | PASSED |
| [`test_router.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_router.py) | `SessionMemory`, `RouteClassifier`, `RetrievalCoordinator` | 6 | PASSED |
| [`test_synthesis.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_synthesis.py) | `CitationValidator`, `AnswerSynthesizer`, `QueryResponseCache` | 9 | PASSED |
| [`test_community.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_community.py) | Label Propagation Algorithm (LPA), community summary synthesis & caching | 9 | PASSED |
| [`test_api.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_api.py) | FastAPI `/query`, `/health`, `/stats`, `/`, `/graph/communities`, `/ingest/paper` | 6 | PASSED |
| [`test_eval.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_eval.py) | `BenchmarkDataset`, `BenchmarkRunner` (un-hardcoded), `BenchmarkReporter` | 3 | PASSED |
| [`test_eval_v2.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_eval_v2.py) | 13 integrity regression properties (paraphrase, hyphens, abstention, contradiction rejection, graph citations) | 13 | PASSED |
| [`test_benchmark_integrity.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_benchmark_integrity.py) | SHA-256 fingerprinting, 50Q balance validation, corpus ID referential integrity | 4 | PASSED |
| [`test_evalkit_adapter.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_evalkit_adapter.py) | `GraphRAGAdapter`, `export_dataset` JSONL conversion | 2 | PASSED |
| [`test_full_evaluation.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_full_evaluation.py) | Metric filtering, hop extraction, legitimacy classification, aggregation & reporting | 20 | PASSED |
| [`test_passage_hydration.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/tests/test_passage_hydration.py) | Graph-guided passage hydration acceptance & adaptive budgeting suite (11 cases: hydration, deduplication, budget cap, empty fallback, deterministic ranking, evaluator recognition, feature flag toggle, latency & token profiling, adaptive budgeting rules) | 11 | PASSED |
| **Subtotal** | **Core Enterprise Pipeline + Evaluation V2 Suite** | **147** | **100% PASSED** |

### 3.2 Evaluation Harness Tests (`evalkit/tests/`)

| Test Module | Target Tested Components | Tests Count | Status |
|---|---|---|---|
| [`evalkit/tests/`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalkit/tests) | Consolidated runner, cache, regression, run store, judges, gates, distributions, shims | 244 | PASSED |
| [`evalkit/tests/test_all_basic_metrics.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalkit/tests/test_all_basic_metrics.py) | All 10 basic metrics computation & runner aggregation | 4 | PASSED |
| [`evalkit/tests/test_graph_metrics.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/evalkit/tests/test_graph_metrics.py) | GraphRAG dimensions: utilization, coherence, diversity, coverage | 5 | PASSED |
| [`scripts/verify_basic_metrics.py`](file:///d:/PROJS/GraphRAG-For-Enterprise-Data/scripts/verify_basic_metrics.py) | Integration suite across all 10 basic metrics + 4 GraphRAG dimensions | 5 suites | PASSED |
| **Subtotal** | **Evaluation Harness & GraphRAG Verification Suites** | **253+** | **100% PASSED** |
| **Repository Total**| **Entire Project Verification Landscape** | **400+** | **100% PASSED** |
