[← README](../README.md)
| [PRD](PRD.md)
| [TRD](TRD.md)
| [Design](DESIGN.md)
| [Architecture](ARCHITECTURE.md)
| [Flows](FLOWS.md)
| [Codebase Map](CODEBASE_MAP.md)
| [Decisions](DECISIONS.md)
| [Tasks](TASKS.md)
| [Scorecard](BENCHMARK_SCORECARD.md)
---

- **Current state**: Production application integration of bounded LangGraph evidence refinement into `src/router/refiner.py` and `src/router/coordinator.py` completed (Phase 36, ADR 070). Codebase sanitized and organized for GitHub: unpushed ad-hoc scripts, raw evaluation run dumps, and legacy shims moved into `_local_archive/` (gitignored). Core test suite 156 / 156 tests passing (100% offline). Verified live FastAPI server execution and multi-tier parity. All canonical docs (`README.md`, `ARCHITECTURE.md`, `FLOWS.md`, `DECISIONS.md`, `CODEBASE_MAP.md`, `TASKS.md`, `BENCHMARK_SCORECARD.md`) fully synchronized.
- **Next step**: Ready for git staging and push to GitHub. Optional local vLLM/Ollama container deployment for low-latency offline inference.

<details>
<summary>Completed Historical Phases (Phases 1–30B)</summary>

## Phase 1 — Extraction into Neo4j
- [x] Corpus: curated arXiv papers, RAG/LLM retrieval subfield
- [x] Pull ~50–150 papers via arXiv API or Semantic Scholar API (with polite rate limits & fallback)
- [x] Finalize ontology (`ONTOLOGY.md` schema implemented in `src/graph/models.py`)
- [x] Chunking pipeline (recursive natural boundaries, 800-char target, 100-char overlap)
- [x] OpenRouter / NVIDIA NIM extraction call with strict schema + retry-on-validation-failure
- [x] Entity resolution (normalize + lexical Jaccard + embedding similarity dedupe + alias storage)
- [x] Neo4j writer using `MERGE` (idempotent), edges carry `source_chunk_id`
- [x] Extraction cache keyed by document/chunk SHA-256 hash

## Phase 2 — Vector index
- [x] Embed same chunks into pgvector with metadata (`document_id`, `section_path`, `entity_ids`)
- [x] HNSW index (`m=16`, `ef_construction=64` with `vector_cosine_ops`)
- [x] Build small labeled recall@k set (`src/vector/tuning.py`)
- [x] Tune `ef_search` against exact ground truth before building retrieval pipelines
- [x] Verify index recall matches or beats unindexed exact search

## Phase 3 — Router
- [x] Router model source: OpenRouter or NVIDIA NIM build
- [x] Build labeled question set for router few-shot examples
- [x] Router call → enum (`graph | vector | both`)
- [x] Low-confidence fallback: run both, merge
- [x] Entity extraction + resolution on incoming questions (`src/graph/query_engine.py`)
- [x] Cypher template library (keyed by query type, model fills params only) (`src/graph/templates.py`)
- [x] Log every routing decision (question, route, outcome)

## Phase 4 — Merge + grounding
- [x] Convert graph paths → readable statements (`GraphQueryEngine.format_records_to_statements`)
- [x] Dedup graph + vector results
- [x] Assemble context with explicit `[graph]` / `[retrieved]` labels
- [x] Require one citation per claim
- [x] Validate citations resolve to actually-retrieved chunk_ids; reject + regenerate on failure

## Phase 5 — Benchmark
- [x] Build 50–100 question eval set, stratified: single-hop, two-hop, three-hop,
      aggregation, out-of-scope (should refuse)
- [x] Run plain vector RAG baseline on the same set
- [x] Run this system on the same set
- [x] Report accuracy by hop count
- [x] Report latency + cost per query, both systems
- [x] Report one-time graph ingestion cost
- [x] Benchmark table → top of README, above architecture diagram

## Ship
- [x] FastAPI `/query` endpoint live
- [x] README benchmark table filled in
- [x] Resume line filled in with real numbers

## Phase 9 — Material 3 Web Interface & Graph API
- [x] Implement `GET /graph/subgraph` in `src/graph/query_engine.py` and `src/api/routes.py`
- [x] Create Material 3 UI assets in `src/api/static/` (`index.html`, `style.css`, `app.js`)
- [x] Build interactive 60 FPS force-directed Neo4j canvas with ontology colors (Vis-Network)
- [x] Build Grounded Chat workspace with route badge (`graph` | `vector` | `both`), latency cards, and citation popover
- [x] Mount `src/api/static` via `StaticFiles` in `src/api/main.py`
- [x] Verify browser interaction and update automated test suite

## Phase 10 — Customizable Ingestion Management & UI Ingestion Dialog
- [x] Define `IngestRequest` and `IngestStatusResponse` schemas in `src/ingestion/models.py` and `src/api/schemas.py`
- [x] Build `IngestionOrchestrator` in `src/ingestion/orchestrator.py` with multi-stage execution and atomic status tracking
- [x] Implement `POST /ingest` and `GET /ingest/status` endpoints in `src/api/routes.py`
- [x] Add M3 Ingestion Dialog and top bar trigger button to `src/api/static/index.html`
- [x] Add M3 Ingestion Dialog styling and linear progress indicator to `src/api/static/style.css`
- [x] Implement dialog event handlers, input validation, and live polling in `src/api/static/app.js`
- [x] Add automated tests for ingestion endpoints in `tests/test_api.py`

## Phase 11 — Chat Session Persistence, Markdown Export & Disconnect Protection
- [x] Add `boot_id` server process UUID to `HealthResponse` schema and `GET /health` in `src/api/schemas.py` and `src/api/routes.py`
- [x] Add `#export-chat-btn` to chat action controls in `src/api/static/index.html` and flex layout in `src/api/static/style.css`
- [x] Implement `sessionStorage` persistence and restoration for `state.chatHistory` across tab changes in `src/api/static/app.js`
- [x] Implement `handleExportChat()` formatted Markdown export generator and client download trigger in `src/api/static/app.js`
- [x] Implement `purgeSessionStorage()` and `handleServerDisconnect()` to auto-clear session storage on server disconnect or `boot_id` reboot in `src/api/static/app.js`
- [x] Add unit test assertions for `boot_id` in `tests/test_api.py`

## Phase 12 — Eager Startup Warmup & Connection Pooling
- [x] Add `warmup()` method to `RetrievalCoordinator` in `src/router/coordinator.py` pre-warming Neo4j Bolt driver and PostgreSQL engine
- [x] Wire eager warmup into `lifespan()` async context manager in `src/api/main.py`
- [x] Update test fixtures in `tests/test_api.py` and add `test_retrieval_coordinator_warmup` in `tests/test_router.py`
- [x] Document ADR 024 in `Docs/DECISIONS.md`

## Phase 13 — Parameterized Ego-Graph Neighborhood Expansion Fallback
- [x] Pre-compile `EGO_NEIGHBORHOOD` Cypher template in `src/graph/templates.py`
- [x] Implement 1-hop connected neighborhood formatting and fallback execution in `src/graph/query_engine.py`
- [x] Add empty-facts escalation from pure graph to hybrid in `src/router/coordinator.py`
- [x] Add unit and integration tests in `tests/test_query_engine.py`
- [x] Document ADR 025 in `Docs/DECISIONS.md`

## Phase 14 — External Evalkit Harness Integration & Decoupled Adapter
- [x] Convert canonical 50-question eval set into `data/evalkit_dataset.jsonl` via `scripts/export_evalkit_dataset.py`
- [x] Implement decoupled `GraphRAGAdapter(BaseAdapter)` in `eval_adapter.py` with dual live HTTP and persistent `AsyncPipelineRunner` execution
- [x] Create multi-track configuration in `evalkit_config.yaml` (`rag` + `text_similarity` tracks)
- [x] Implement `run_evalkit.py` execution runner producing `data/evalkit_report.md` and `data/evalkit_results.json`
- [x] Add automated unit tests in `tests/test_evalkit_adapter.py` (2/2 passing; 54/54 overall)
- [x] Document ADR 029 in `Docs/DECISIONS.md`

## Stretch (post-launch)
- [x] Incremental graph updates instead of full reingestion (`POST /ingest/paper`, chunk hashing in `orchestrator.py`, `delete_chunks`, `delete_edges_for_chunks`)
- [x] Community detection for corpus-level summaries (pure-Python LPA, `GET /graph/communities`, `GraphCommunityDetector` in `src/graph/community.py`, thematic injection in coordinator)
- [x] Response UI inline graph visualization (Vis-Network canvas container, toggle button, dynamic subgraph extraction in `QueryResponse`)

## Phase 15 — Full Benchmark Evaluation Harness & Score Legitimacy Auditing
- [x] Implement standalone multi-track evaluation runner in `scripts/run_full_evaluation.py`
- [x] Support full 50-question evaluation dataset stratified across 5 hop tiers (`1-hop`, `2-hop`, `3-hop`, `aggregation`, `out-of-scope`)
- [x] Dynamically detect missing dependencies (`sacrebleu`, `rouge_score`) to avoid runtime crashes
- [x] Implement score legitimacy taxonomy (`deterministic`, `judge-scored`, `pseudo-random`)
- [x] Support dual mode operation: `--mode dummy` (offline) and `--mode live` (LiteLLM judge)
- [x] Add spot-check sample generator for manual human verification in `spot_check_samples.md`
- [x] Create comprehensive unit test suite in `tests/test_full_evaluation.py` (20/20 passing; 83/83 overall)
- [x] Update living docs (`DECISIONS.md` ADR 031, `CODEBASE_MAP.md`, `TASKS.md`)
- [x] Execute full 50-question live LLM-judged benchmark run via NVIDIA NIM and generate authentic scores in `data/full_evaluation/`

## Phase 16 — Evaluation-Integrity Refactor & Decoupled 5-Layer Benchmark Standard (Evaluation V2)
- [x] Implement shared Unicode and lexical normalizer in `src/eval/text_norm.py` (NFKC, lowercase, apostrophe & hyphen `‐ ‒ – — ― − -` -> `-`, whitespace)
- [x] Add unit tests in `tests/test_text_norm.py` verifying hyphen and apostrophe equivalence (4/4 passed)
- [x] Author structured fact ground-truth dataset in `data/benchmark_v2_dataset.jsonl` (50 questions with atomic `required_facts`, weights, clean reference answers, and explicit `answerable` flags)
- [x] Build decoupled 5-layer evaluator engine in `src/eval/evaluator_v2.py` (Retrieval, Factual Correctness, Groundedness, Answerability, Efficiency)
- [x] Purge all synthetic question-ID overrides (`is_accurate = False`) and `matches > 0` single-keyword shortcuts from `src/eval/runner.py`
- [x] Create comprehensive regression test suite in `tests/test_eval_v2.py` covering all 9 integrity properties (9/9 passed; 96/96 overall)
- [x] Update model configuration to active `meta/llama-3.2-11b-vision-instruct` following NVIDIA NIM deprecation of legacy Nemotron
- [x] Execute complete V2 benchmark run via `scripts/run_benchmark_v2.py` producing `data/benchmark_results_50q_v2.json`, `data/benchmark_audit_records_v2.jsonl`, `data/benchmark_audit_table_v2.md`, and `data/benchmark_comparison_v1_vs_v2.json`
- [x] Preserve legacy v1 results untouched in `data/test_evaluation_bundle/benchmark_results_50q.json`
- [x] Document ADR 034 in `Docs/DECISIONS.md` and update `Docs/CODEBASE_MAP.md`

## Phase 17 — Evaluation Harness Unification & Complete 10-Metric Suite
- [x] Extract `evalharness` from `evalharness.zip` and install editable in virtual environment
- [x] Fix Windows CP1252 default encoding bugs across `evalharness/core/report.py`, `dataset.py`, `config.py` and `tests/test_report.py` (explicit `encoding="utf-8"`)
- [x] Port `AdapterResponse` into `evalharness/contracts/adapter.py` supporting dynamic context overrides, latency tracking, and custom metadata
- [x] Port structured JSON judge output parsing (`response_format: json_object`), fallback retry, code fence stripping, and $[0.0, 1.0]$ bounds validation into `evalharness/judges/litellm_judge.py`
- [x] Wire dynamic context override, latency extraction, and dollar `cost` estimation into `evalharness/core/runner.py` and `report.py`
- [x] Implement Normalized Discounted Cumulative Gain (`ndcg_at_k`) with position discounting $\frac{2^{rel_i}-1}{\log_2(i+2)}$ in `evalharness/evaluators/retrieval.py` and `evalkit_upgraded/evalkit/evaluators/retrieval.py`
- [x] Implement LLM-judge evaluated `context_recall` and `answer_correctness` in `evalharness/evaluators/rag.py` and `evalkit_upgraded/evalkit/evaluators/rag.py`
- [x] Implement BERTScore (`bert_score_f1`) in `evalharness/evaluators/text_similarity.py` with memory-safe fallback to lexical overlap on paging limits
- [x] Implement unit test suite verifying all 10 metrics compute and aggregate in `evalkit_upgraded/tests/test_all_basic_metrics.py` (4/4 passed)
- [x] Implement deterministic, sub-second unit test suite in `evalharness/tests/test_all_basic_metrics.py` (4/4 passed)
- [x] Verify standalone aggregation script `scripts/verify_basic_metrics.py` passing across all 10 metrics
- [x] Verify core repository test suite remains 100% green (`pytest tests`: 96/96 passed)
- [x] Document ADR 035 in `Docs/DECISIONS.md` and update `Docs/CODEBASE_MAP.md`

## Phase 18 — GraphRAG Evaluation Matrix Implementation
- [x] Build `GraphEvaluator` in `evalharness/evaluators/graph.py` implementing all 3 GraphRAG layers:
  - Layer 1 (Indexing): `entity_relation_coverage` (set-based & prompt-based recall) and `community_coherence` (LLM-judge evaluation of cluster summaries against member chunks)
  - Layer 2 (Search): `graph_utilization_rate` (ratio of retrieved graph statements/subgraph edges actually utilized in output)
  - Layer 3 (Generation): `global_diversity` (lexical unigram/bigram entropy + thematic cluster coverage for aggregation queries)
- [x] Implement identical `GraphEvaluator` in `evalkit_upgraded/evalkit/evaluators/graph.py`
- [x] Register `"graph"` evaluation track in `evalharness/__init__.py` and `evalkit_upgraded/evalkit/__init__.py`
- [x] Extend `eval_adapter.py` `AdapterResponse.metadata` with `graph_facts_retrieved`, `expected_themes`, `community_summary`, and `community_chunks`
- [x] Author comprehensive unit tests in `evalharness/tests/test_graph_metrics.py` (5/5 passed)
- [x] Author unit tests in `evalkit_upgraded/tests/test_graph_metrics.py` (5/5 passed)
- [x] Update `scripts/verify_basic_metrics.py` with GraphRAG dimension validation (all 10 basic metrics + 4 GraphRAG dimensions passing)
- [x] Verify core repository test suite remains 100% green (`pytest tests`: 96/96 passed)
- [x] Document ADR 036 in `Docs/DECISIONS.md` and update `Docs/CODEBASE_MAP.md`

## Phase 19 — Comparative Benchmark Audit (Evalkit vs. RAGAS on GraphRAG)
- [x] Install `ragas` v0.4.3 in `.venv` and configure with NVIDIA NIM (`ChatOpenAI` + `OpenAIEmbeddings` with `check_embedding_ctx_length=False`)
- [x] Implement comparative benchmark driver `scripts/compare_evalkit_vs_ragas.py` querying GraphRAG application via `GraphRAGAdapter`
- [x] Execute dual evaluation across 5 stratified complexity tiers (`1-hop`, `2-hop`, `3-hop`, `aggregation`, `out-of-scope`)
- [x] Compute side-by-side metric calibration (MAE = 0.0975 on `context_precision`)
- [x] Evaluate unique GraphRAG dimensions via Evalkit (`graph_utilization_rate` = 0.6000, `global_diversity` = 0.8742)
- [x] Document abstention failure in RAGAS (scored 1.000 recall/relevancy on out-of-scope biology question) vs. Evalkit (properly scored 0.000)
- [x] Generate audit artifacts `data/evalkit_vs_ragas_comparison.md` and `data/evalkit_vs_ragas_comparison.json`
- [x] Document ADR 037 in `Docs/DECISIONS.md` and update `Docs/CODEBASE_MAP.md`

## Phase 20 — Adoption of Evalkit as Authoritative Enterprise Benchmark Runner
- [x] Upgrade `LiteLLMJudge` in `evalharness` and `evalkit_upgraded` with auto-resolution of `api_base` and `api_key` from `src.core.config.get_settings()`
- [x] Add flexible field coercion (`question` -> `input`, `reference_answer` -> `reference`, packing extras into `metadata`) in `evalharness.core.dataset.EvalExample`
- [x] Configure authoritative multi-track benchmark in `evalkit_config.yaml`:
  - Tracks: `[rag, retrieval, graph, text_similarity]`
  - Dataset: `data/benchmark_v2_dataset.jsonl`
  - Adapter: `eval_adapter:GraphRAGAdapter`
  - Judge: `openai/meta/llama-3.2-11b-vision-instruct` via LiteLLM
  - Caching & Concurrency: File-cached with atomic locking
- [x] Transition `run_evalkit.py` to `evalharness` engine with rich run info and dual Markdown/JSON reporting
- [x] Execute authoritative evaluation run producing `data/evalkit_report.md` and `data/evalkit_results.json`
- [x] Document ADR 038 in `Docs/DECISIONS.md` and update `Docs/CODEBASE_MAP.md`
- [x] Verify core test suite remains 100% green (`pytest tests`: 96/96 passed)

## Phase 21 — External Fireworks AI Judge Adoption & Ground-Truth Retrieval Ranking
- [x] Integrate Fireworks AI `fireworks_ai/accounts/fireworks/models/deepseek-v4p1-flash` via `evalkit_config.yaml`
- [x] Harden `LiteLLMJudge` token limit handling (3000 max tokens + 1500 headroom on retry) and `reasoning_content` fallback
- [x] Populate ground-truth `gold_chunk_ids` across all 50 questions in `data/benchmark_v2_dataset.jsonl` matching ingested pgvector chunk IDs
- [x] Update `RetrievalEvaluator` in `evalharness` and `evalkit_upgraded` to accept `gold_chunk_ids` metadata alias and match bracketed citations without substring collisions
- [x] Align `mrr` and `ndcg_at_k` to test hit membership against retrieved chunks
- [x] Execute 14-metric authoritative benchmark run across 5 stratified complexity tiers (<$0.01 Fireworks cost)
- [x] Document ADR 039 in `Docs/DECISIONS.md`
- [x] Verify 100% green test passes across retrieval, judge, and core suites
- [x] Re-package sanitized `GraphRAG_Enterprise_Codebase.zip` (239 files, 0.67 MB) containing updated docs, tests, benchmark data, and `evalharness`

## Phase 22 — Consolidation & Cleanup of `evalkit` Package
- [x] Merge core execution harness (`cache.py`, `regression.py`, `run_store.py`, `stats.py`, runner, CLI) into `evalkit/evalkit`
- [x] Rename directory `evalkit_upgraded/` to canonical `evalkit/` and install via `pip install -e evalkit`
- [x] Register dual console scripts (`evalkit` and `evalharness` pointing to `evalkit.cli:main`) in `evalkit/pyproject.toml`
- [x] Deploy lightweight forwarding proxy shims across 29 modules in `evalharness/` for zero-breakage backward compatibility
- [x] Consolidate authoritative test suite in `evalkit/tests/` (89 tests verified 100% passing across basic metrics, retrieval, judges, cache, and regression)
- [x] Document ADR 040 in `Docs/DECISIONS.md`
- [x] Update `evalkit_config.yaml` to specify unified evalkit framework
- [x] Purge test caches (`.evalharness/cache/`, `.pytest_cache/`, `__pycache__/`, transient slices `data/temp_*`, stale zip archives)
- [x] Harden `.gitignore` with `.evalharness/`, `data/neo4j/`, `data/postgres/`, and `temp_*`

## Phase 23 — Evaluation V2 Integrity & Anti-Contamination Adoption
- [x] Implement `src/eval/benchmark_integrity.py` with dataset SHA-256 fingerprinting and strict 50Q validation (40 answerable, 10 unanswerable)
- [x] Enforce non-evaluable `None` metrics when gold retrieval labels are missing in `EvaluatorV2.evaluate_retrieval`
- [x] Decouple factual correctness from abstention scoring in `EvaluatorV2.evaluate_facts` (`fact_score=None` on unanswerable)
- [x] Implement local contradiction negation detection (`_is_negated_occurrence`)
- [x] Expand citation evidence universe to include Neo4j graph facts (`extract_graph_evidence_ids`)
- [x] Enforce fail-closed zero-leakage error handling in `src/eval/runner.py` and `scripts/run_benchmark_v2.py`
- [x] Mark historical benchmark artifacts as `STALE_UNTRUSTED_PRE_FIX` in `data/benchmark_results_50q_v2.json` and `data/EVALUATION_ARTIFACT_STATUS.md`
- [x] Add standalone pre-flight scripts `scripts/validate_benchmark_v2_dataset.py` and `scripts/audit_eval_v2.py`
- [x] Verify all 17 V2 integrity unit tests passing (`tests/test_eval_v2.py`, `tests/test_benchmark_integrity.py`)
- [x] Document ADR 041 in `Docs/DECISIONS.md`
- [x] Preserve Phase 22 unified `evalkit` architecture and reject directory reversions

## Phase 24 — Retrieval Evaluator Upper-Bound Hardening & Fresh Benchmark Regeneration
- [x] Fix hit-multiplication recall and NDCG explosion bug in `evalkit/evalkit/evaluators/retrieval.py` via `_extract_chunk_ids` first-seen source chunk deduplication and $[0.0, 1.0]$ boundary clamping (ADR 044)
- [x] Add regression test `test_multi_edge_duplicate_source_chunks_cap_recall_at_one` in `evalkit/tests/test_retrieval.py` (12/12 passing)
- [x] Execute fresh 50-question Benchmark V2 (`data/benchmark_results_50q_v2.json`, SHA-256: `7cc148cb...`, 100 audit records) with status `fresh_run`
- [x] Regenerate authoritative evalkit report (`data/evalkit_report.md`, `data/evalkit_results.json`) confirming `recall_at_k <= 1.000` and `ndcg_at_k <= 1.000`
- [x] Update `data/evalkit_vs_ragas_comparison.md` replacing calibration terminology with "Score Gap" analysis
- [x] Update `data/EVALUATION_ARTIFACT_STATUS.md` recording fresh-run status and mathematical upper-bound enforcement
- [x] Package 23-file authoritative `GraphRAG_Evaluation_Results_Bundle.zip` (SHA-256: `7edaf8c0...`)

## Phase 25 — A/B/C/D Ablation & Causal Diagnostic Gate (Types A–F)
- [x] Author 4-way ablation driver in `scripts/run_abcd_ablation.py` (Vector vs. Graph vs. Hybrid vs. Oracle)
- [x] Implement strict zero-leakage Oracle mode (gold chunks only, no expected answers or required facts)
- [x] Implement extended telemetry (estimated tokens, unique evidence IDs, retrieval metrics, latency, citation validity, abstention)
- [x] Integrate 4-stage pipeline audit table (`Retrieval | Evidence | Context | Generation | Failure`)
- [x] Implement Types A–F failure taxonomy triage for worst Hybrid cases
- [x] Fix signature mismatch in `EvaluatorV2.evaluate_question` call
- [x] Execute and verify 5-question stratified smoke test producing `data/abcd_ablation_report.md`
- [x] Document ADR 047 in `Docs/DECISIONS.md`
- [x] Execute full 50-question A/B/C/D ablation run without cache or dialogue history contamination
- [x] Triage worst 10 Hybrid cases across Types A–F failure taxonomy (`data/abcd_ablation_report.md`)

## Phase 26 — Evaluator V2 Four-Safeguard Remediation & Ground-Truth Verification
- [x] Step 1: Implement Safeguard 1 in `EvaluatorV2`: Refusal never erases already-satisfied facts (`answer -> facts -> contradiction -> refusal check`)
- [x] Step 1: Implement Safeguard 2 in `EvaluatorV2`: Per-fact semantic judge fallback with strict context isolation (receives only Question, Generated Answer, Atomic Fact)
- [x] Step 1: Implement Safeguard 3 in `EvaluatorV2`: Contradiction overrides entailment in lexical and semantic evaluations
- [x] Step 1: Implement Safeguard 4 in `EvaluatorV2`: Preserve evidence trail in `QuestionAuditRecord.fact_verdicts` (`fact_id`, `status`, `method`, `lexical_match`, `contradicted`, `judge_score`, `reasoning`)
- [x] Step 1: Fix clause-boundary bleed in `_is_negated_occurrence` to prevent subsequent sentences from triggering false contradictions
- [x] Step 1: Add 5 regression tests in `tests/test_eval_v2.py` verifying all four safeguards (18/18 passing)
- [x] Step 1: Verify key acceptance tests (`q_agg_01` 0.0 -> 1.0, `q_agg_09` 0.0 -> 1.0, `q_2hop_06` 0.0 -> 1.0, `q_3hop_09` 0.0 -> 1.0)
- [x] Step 1: Document ADR 048 in `Docs/DECISIONS.md`
- [x] Step 2: Produce G1 (missing in corpus) vs. G2 (source mismatch: metadata/graph vs. chunk abstract) audit table before modifying `benchmark_v2_dataset.jsonl`
- [x] Step 3: Execute clean 50Q A/B/C/D ablation rerun comparing Vector, Graph, Hybrid, and Oracle with repaired EvaluatorV2

## Phase 27 — Dedicated MetadataResolver Evaluation (Run 2)
- [x] Implement provenance-aware `MetadataResolver` (`src/router/metadata_resolver.py`) indexing `papers.json`
- [x] Integrate `metadata_records` into `RetrievalContext` and `RetrievalCoordinator.retrieve`
- [x] Format catalog headers in `AnswerSynthesizer.assemble_context`
- [x] Unit test suite verified (7/7 passing in `tests/test_metadata_resolver.py`)
- [x] Execute clean 50Q Run 2 evaluation (`scripts/run_metadata_ablation_run2.py`)
- [x] Document ADR 051 in `Docs/DECISIONS.md`
- [x] Analyze Run 2 findings: metadata recall recovered to 1.0000, but revealed incidental author trigger bug (`q_2hop_02`) and placeholder conflict (`q_1hop_04`)

## Phase 28 — Evidence Precedence & Placeholder Conflict Suppression (Run 3A)
- [x] Tighten `MetadataResolver` trigger with `INCIDENTAL_AUTHOR_PATTERN` to prevent incidental author mentions from activating catalog headers
- [x] Implement Step 3d Evidence Precedence & Conflict Suppression in `RetrievalCoordinator.retrieve` (suppress `Unknown Author` when authoritative catalog metadata exists)
- [x] Add `suppressed_evidence` provenance ledger to `RetrievalContext`
- [x] Add Rule 6 (Evidence Precedence) to `SYNTHESIS_SYSTEM_PROMPT` in `src/synthesis/synthesizer.py`
- [x] Filter `retrieved` and `graph` reserved tags from `CitationValidator.extract_citations`
- [x] Expand unit tests in `tests/test_metadata_resolver.py` (9/9 passing)
- [x] Verify focused 4-question acceptance criteria (`q_1hop_01` 1.0, `q_1hop_04` 1.0 with catalog winning, `q_2hop_02` 1.0 with 0 catalog headers)
- [x] Document ADR 052 in `Docs/DECISIONS.md`
- [x] Execute full 50Q Run 3A benchmark (`scripts/run_precedence_ablation_run3a.py`) comparing Run 1 vs Run 2 vs Run 3A
- [x] Verify acceptance metrics: Fact score 0.7458 (+0.0708 vs Run 1, +0.1000 vs Run 2), Strict success 60.0% (+17.5%), Non-metadata slice 0.7252 (+0.0811 vs Run 2), Metadata slice 1.0000

## Phase 29 — Canonical Title & Entity Parameter Resolution in Cypher (Run 3B)
- [x] Annotate all 30 Neo4j `Paper` nodes with authoritative `p.id` accession properties mapped from corpus catalog (`arxiv_YYMM.NNNNNvV`)
- [x] Implement deterministic 6-tier `CanonicalEntityResolver` (`src/graph/canonical_resolver.py`):
  1. Canonical ID
  2. Exact normalized arXiv ID regex
  3. Exact normalized title/name
  4. Curated alias table (`CURATED_ENTITY_ALIASES`)
  5. Controlled token similarity (Jaccard $\ge 0.85$)
  6. Ambiguity gate & rejection (`top_score < 0.85` OR `top_score - second_score < 0.15` rejects)
- [x] Authoritative Cypher Binding: converted all paper and entity Cypher templates in `src/graph/templates.py` to exact parameterized equality (`($canonical_id <> '' AND p.id = $canonical_id) OR toLower(p.name) = toLower($paper_title)`)
- [x] Integrated pre-execution gating in `GraphQueryEngine.execute_query` to cleanly skip Cypher execution on rejected/ambiguous targets
- [x] Added candidate evaluation audit ledger recording full candidate set, top score, second score, ambiguity count, and acceptance status
- [x] Unit test suite verified (13/13 passing in `tests/test_canonical_resolver.py` and `tests/test_query_engine.py`)
- [x] Focused 5-question acceptance suite verified (3/3 target resolution accuracy, 0/5 wrong-match rate, 1/1 ambiguous correctly rejected, 1/1 negative correctly rejected)
- [x] Documented ADR 053 in `Docs/DECISIONS.md`
- [x] Run full 50Q Run 3B benchmark comparing Run 1 vs Run 2 vs Run 3A vs Run 3B (`scripts/run_canonical_ablation_run3b.py`)
- [x] Verify acceptance metrics: target resolution accuracy 100.0%, wrong-match rate 0.0%, Type-B graph recall 0.8000 (+0.2000), overall graph recall 0.5897 (+0.1153), unified recall 0.6708 (+0.0750), fact score 0.7583 (+0.0125), non-Type-B fact score 0.7333 (+0.0143)

## Phase 30 — Relational Traversal Path & Graph Fact Statement Formatting
- [x] Redesign `GraphQueryEngine.format_records_to_statements` to serialize explicit directed relational paths (`--[:REL]-->`, `<--[:REL]--`) with ontology directionality
- [x] Format multi-hop lineage chains (`METHOD_ANCESTRY_EXTENDS`) and citation chains (`CITATION_CHAIN`) with sequential steps (`A → B → C`) and conclusions
- [x] Format benchmark comparisons (`METHOD_BENCHMARK_COMPARISONS`) as bipartite paths through shared datasets and individual paper nodes
- [x] Enforce non-inventive edge guardrail: zero ungrounded/inferred edges; all paths strictly project actual Neo4j query rows
- [x] Fix multi-chunk provenance tagging to format as individual `[chunk: {c}]` tags for 100% extraction into `graph_evidence_ids`
- [x] Update and verify unit test assertions in `tests/test_query_engine.py` (13/13 passing)
- [x] Empirical verification audit: Unified recall 0.6708 (stable), graph recall 0.5897 (stable), metadata recall 1.0000 (stable); overall fact score regressed 0.7583 → 0.7417 (-0.0166) and strict success dropped 60.0% → 52.5% (-7.5%) due to +134.1 context tokens bloating single-hop prompts (0.8000 → 0.7000). Phase 30 primary acceptance criteria failed.

## Phase 30B — Concise Relational Serialization & De-bloating Benchmark
- [x] Strip verbose `Path: ... Therefore, ...` prose boilerplate from `format_records_to_statements` while retaining directional relation syntax (`--[:REL]-->`, `<--[:REL]--`) and `[chunk: {c}]` provenance tags
- [x] Verify unit test assertions in `tests/test_query_engine.py` (22/22 passing)
- [x] Document ADR 055 in `Docs/DECISIONS.md`
- [x] Create benchmark script with exact side-by-side context audit logging (`scripts/run_path_formatting_phase30b.py`)
- [x] Run full 50Q Phase 30B benchmark comparing Run 1 vs Run 2 vs Run 3A vs Run 3B vs Phase 30 vs Phase 30B
- [x] Empirical verification audit: Mean context tokens fell from 526.3 to 392.3 (-134.0 tokens, matching Run 3B's 392.2). Strict success recovered from 52.5% to 55.0% (+2.5%), fact score recovered from 0.7417 to 0.7500 (+0.0083), and single-hop recovered from 0.7000 to 0.7500 (+0.0500). However, Phase 30B failed Run 3B acceptance thresholds (strict success 55.0% < 60.0%, fact score 0.7500 < 0.7583, single-hop 0.7500 < 0.8000).
- [x] Roll back `format_records_to_statements` to Run 3B format while retaining `[chunk: {c}]` provenance extraction fix and freeze Run 3B as production baseline (ADR 056)
- [x] Verify unit test suite with rolled-back format (22/22 passing)

</details>

## Phase 31 — Generator & Context Diagnostics on Remaining Failed Questions
- [x] Phase 31A: Implement channel-strict evidence accounting in `EvaluatorV2`, disentangling graph provenance chunk tags from retrieved document passages (ADR 057)
- [x] Phase 31A: Add synthetic isolation unit test `test_graph_provenance_does_not_inflate_substantive_or_unified_recall` (20/20 test_eval_v2.py passing, 136/136 full repo passing)
- [x] Phase 31B: Recompute frozen Run 3B baseline under channel-strict accounting: unified evidence recall corrected from 0.6708 to 0.3083 (-0.3625), substantive chunk recall 0.2821, metadata recall 1.0000, fact score stable at 0.7583, strict success stable at 60.0% answerable (68.0% overall)
- [x] Phase 31C: Execute Oracle control across all 16 failed questions under identical generator (Qwen2.5-7B, temp=0.0) and prompt settings (ADR 058)
- [x] Phase 31C: Analyze results against predetermined interpretation rubric: 13/16 (81.3%) convert to strict passes (mean fact score 0.3958 → 0.8646, +0.4688), confirming retrieval deficiency as primary causal bottleneck rather than generator synthesis capacity
- [x] Phase 31D: Audit remaining 3 non-passing Oracle cases (`q_2hop_03`, `q_2hop_10`, `q_3hop_05`): classified 2 as Annotation Defects and 1 as Question/Source Premise Mismatch; zero generator capacity failures detected; frozen benchmark preserved 100% untouched (ADR 059)

## Phase 32 — Multi-Hop Retrieval Expansion
- [x] Step 32A: Implement `VectorStore.get_chunks_by_ids` using indexed primary key batch query (`WHERE chunk_id = ANY(:chunk_ids)`) preserving deterministic input ordering
- [x] Step 32A: Add configuration settings `enable_graph_passage_hydration: bool = False` and `max_graph_hydrated_passages: int = 3` to `Settings`
- [x] Step 32A: Implement deterministic chunk selection rule in `RetrievalCoordinator.retrieve()`: candidate graph chunk IDs filtered against vector hits, ranked by topological relevance (frequency descending, tie-broken by first-seen traversal index), capped to top $\le 3$ passages
- [x] Step 32A: Add auditable telemetry fields to `RetrievalContext`: `candidate_graph_chunk_ids`, `selected_graph_chunk_ids`, `hydrated_chunk_ids`, `dropped_due_to_budget`, and `latencies["graph_hydration_ms"]`
- [x] Step 32A: Author and pass pre-registered 8-case acceptance test suite (`tests/test_passage_hydration.py`):
  1. Graph returns `chunk_X`, vector did not $\rightarrow$ `chunk_X` hydrated into `retrieved_chunks`
  2. Vector already returned `chunk_X` $\rightarrow$ deduplicated (exactly 1 copy)
  3. Graph returns 10 chunks $\rightarrow$ capped to $\le 3$ graph-expanded passages
  4. Graph returns 0 chunks $\rightarrow$ behavior identical to Run 3B
  5. Ordering/ranking is 100% deterministic across repeated queries
  6. Corrected evaluator recognizes hydrated chunks as substantive evidence (substantive & unified recall rise from 0.0 to 1.0)
  7. Feature flag toggle `enable_graph_passage_hydration=False` preserves Run 3B identically
  8. Batch lookup latency measured (p50=5.49ms, p95=19.88ms in unit; p50=6.48ms in live smoke; no hardcoded claims) and context-token budget verified
- [x] Step 32A: Verify entire repository test suite remains 100% green (144/144 tests passing)
- [x] Step 32A: Document ADR 060 in `Docs/DECISIONS.md`
- [x] Step 32B: Execute full 50Q benchmark comparing frozen Run 3B baseline vs Step 32A Multi-Hop Passage Hydration against pre-registered engineering gates (`scripts/run_phase32b_benchmark.py`, ADR 061)
- [x] Step 32C: Implement evidence-gap adaptive passage hydration policy (`compute_adaptive_hydration_budget`) with 4 deterministic branches and query decision logging
- [x] Step 32C: Add configuration toggle `enable_adaptive_hydration: bool = True` preserving 32B control when disabled
- [x] Step 32C: Author unit and acceptance tests for pure budgeting rule, telemetry, and 32B toggle ablation (`tests/test_passage_hydration.py`, 11/11 passing)
- [x] Step 32C: Execute full 50Q benchmark (`scripts/run_phase32c_benchmark.py`) comparing Step 32C vs Step 32B vs Run 3B against 8 pre-registered preservation gates (ADR 062, `data/phase32c_adaptive_hydration_report.md`):
  - 1 of 8 gates passed (Invalid Citations: 0.0%)
  - Failed preservation gates: Mean Context Tokens = 541.7 vs <= 450.0, Fact Score = 0.7958 vs >= 0.8208, Strict Success = 27/40 vs >= 28/40, Substantive Recall = 0.5513 vs >= 0.6538, Unified Recall = 0.5708 vs >= 0.6708, P50 Latency = 4660.2 ms vs <= 4500.0 ms, 1-Hop Fact Score = 0.7000 vs >= 0.8000
  - Causal analysis: Heuristic policy under-hydrated necessary multi-hop chunks (`q_2hop_06` fell 1.0 -> 0.0; `q_3hop_06` fell 1.0 -> 0.67) while insufficiently compressing context (541.7 tokens)
  - Decision: Step 32C rejected; Step 32B frozen as current performance control/champion for Phase 33

## Phase 33 — Final Re-Benchmark & Release
- [x] Step 33A: Lock retrieval evaluation configuration (Step 32B Multi-Hop Passage Hydration, static cap=3, adaptive hydration disabled)
- [x] Step 33A: Run fresh full repository test suite against frozen state (`pytest tests`: 147 passed, 1 warning in 43.51s, 100% green)
- [x] Step 33B: Run final end-to-end regression benchmark across all 50 questions (`scripts/run_phase33_release_benchmark.py`)
- [x] Step 33B: Verify 100% deterministic retrieval reproducibility:
  - Retrieved chunk IDs identical: 50/50 (100.0%)
  - Graph facts identical: 50/50 (100.0%)
  - Substantive chunk recall: 0.6538 (100.0% preserved)
  - Unified evidence recall: 0.6708 (100.0% preserved)
  - Mean context tokens: 598.0 (100.0% preserved)
  - Invalid citation rate: 0.0% (100.0% preserved)
  - Out-of-scope abstention: 10/10 (100.0% preserved)
  - Fact score stability: 46/50 (92.0%) questions identical; 4 questions varied due to remote API token generation phrasing (fact score 0.8000 vs 0.8208, strict success 26/40 vs 28/40)
- [x] Step 33C: Apply explicit release criteria:
  - Required quality criteria: Substantive recall (0.6538), unified recall (0.6708), and invalid citations (0.0%) pass; fact score (0.8000 < 0.8208 -> FAIL) and strict success (26/40 < 28/40 -> FAIL) failed pre-registered thresholds due to downstream remote NIM generation phrasing variance; P50 latency (5043.9 ms > 4500.0 ms -> FAIL) failed due to remote gateway queue times
  - Efficiency criterion: Mean context 598.0 tokens resolved as an explicit accepted limitation of the champion ("Quality/retrieval objectives achieved; context-efficiency objective remains unresolved and is an accepted limitation of the final champion")
  - Release status: Withheld. Step 32B accepted as research champion / release candidate, not reproducibly release-qualified yet
- [x] Step 33C: Finalize canonical documentation (`Docs/DECISIONS.md` ADR 063, `Docs/CODEBASE_MAP.md`, `Docs/TASKS.md`, `README.md`) and archive release artifacts (`data/phase33_final_release_results.json`, `data/phase33_final_release_audit.jsonl`, `data/phase33_final_release_report.md`)
- [x] Step 33D: Execute frozen repeatability study across repeated 50Q runs (`scripts/run_phase33d_repeatability_study.py`, ADR 064):
  - Evaluated 3 independent frozen runs (Run 1: 32B peak; Run 2: P33 rerun 1; Run 3: P33 rerun 2)
  - Retrieval determinism: 100% identical (50/50 candidate chunks, 50/50 graph facts, 50/50 hydrated passages; substantive recall 0.6538, unified recall 0.6708, invalid citations 0.0%)
  - Downstream variance quantified: Fact score 0.8042 ± 0.0150 (range [0.7917, 0.8208]); Strict success 26.3 ± 1.5 / 40 (range [25, 28], 62.5%–70.0%)
  - Per-question stability: 44/50 (88.0%) questions 100% stable; audit attributes the 6 unstable cases to answer-generation phrasing variation
  - Latency decomposed: Remote NIM generation is the largest measured median component (1979.1 ms, ~52.4%), while local DB retrieval (411.9 ms) and passage hydration (8.2 ms) contribute substantially less (~11.1% combined); mean of run-level P50 medians is 4311.4 ms
  - Final Classification: Research Champion / Release Candidate (Quantified Generator Variance)
  - Artifacts produced: `data/phase33d_repeatability_results.json`, `data/phase33d_repeatability_report.md`, `data/phase33d_run3_audit.jsonl`

## Phase 34 — LangGraph Exploration & Hybrid Refinement
- [x] Standalone LangGraph Orchestration & Benchmark (ADR 067):
  - Implemented 9-node `StateGraph` in `scripts/langgraph_graphrag.py` with cyclical citation self-correction loop and 0 touch to `src/`.
  - Built `scripts/langgraph_adapter.py` connecting LangGraph to `evalkit`.
  - Evaluated stratified sample (`data/langgraph_benchmark_results.json`): fact score 0.8750 (+7.5%), strict success 75.0% (+10.0%), invalid citations 0.0%, P50 latency 37.1s.
- [x] Hybrid 32B Champion with Bounded 1-Pass LangGraph Evidence Refinement (ADR 068):
  - Preserved Phase 32B `RetrievalCoordinator` as fast primary path (~80% fast path).
  - Built heuristic zero-LLM evidence gap detector checking missing corpus entities and documents.
  - Implemented 3-node bounded refinement `StateGraph` (`isolate_gap_node` -> `targeted_retrieval_node` -> `merge_evidence_node`) in `scripts/langgraph_evidence_refinement.py`.
  - Built isolated benchmark runner `scripts/run_evidence_refinement_benchmark.py`.
  - Evaluated stratified sample (`data/evidence_refinement_benchmark_results.json`): fact score 1.0000 (+20.0% vs P33 baseline), strict success 100.0% (+35.0%), invalid citations 0.0%, P50 latency 6,148.1 ms (~83% latency reduction vs standalone LangGraph).
- [x] Full 50-Question Benchmark under Pre-Registered Gates (ADR 068):
  - Pre-registered all 10 engineering gates and strict isolation protocols prior to running full benchmark.
  - Executed across all 50 canonical questions with complete isolation (`use_cache=False`, fresh sessions, unshared artifacts).
  - Fact score: **0.8667** vs $\ge 0.8208$ target (PASSED, +0.0667 vs 0.8000 baseline).
  - Strict success rate: **72.5%** (29/40) vs $\ge 70.0\%$ target (PASSED, +7.5% vs 65.0% baseline).
  - Substantive chunk recall: **0.7179** vs $\ge 0.6538$ target (PASSED, +0.0641 vs baseline).
  - Unified evidence recall: **0.7333** vs $\ge 0.6708$ target (PASSED, +0.0625 vs baseline).
  - Invalid citation rate: **0.0%** (PASSED, 0 invalid citations across all 50 questions).
  - Hop-tier parity: 1-hop fact score **0.8000** (0 regression), OOS abstention **100.0%** (10/10, 0 regression).
  - Refinement telemetry: Fast path rate **54.0%** (27/50 queries), Refinement activation rate **46.0%** (23/50 queries).
  - P50 latency: **7,283.0 ms** (~80% reduction vs standalone LangGraph's 37.1s).
- [x] 3-Run Hybrid Repeatability Study (Phase 34 Repeatability Qualification):
  - Built runner `scripts/run_hybrid_repeatability_study.py` executing Run 2 and Run 3 under frozen parameters with Run 1 ingested from audit.
  - Quality criteria verified:
    - Mean Fact Score: **0.8722 ± 0.0064** (range [0.8667, 0.8792]) vs $\ge 0.8208$ target -> **PASSED**.
    - Mean Strict Success: **75.0% ± 2.5%** (30.0/40) vs $\ge 28/40$ ($70.0\%$) target -> **PASSED**.
    - Mean Substantive Chunk Recall: **0.7179** vs $\ge 0.6538$ target -> **PASSED**.
    - Mean Unified Evidence Recall: **0.7333** vs $\ge 0.6708$ target -> **PASSED**.
    - Invalid Citations: **0.0%** on every run -> **PASSED**.
    - OOS Abstention: **10/10 (100.0%)** on every run -> **PASSED**.
    - Retrieval Determinism: **50/50 (100.0%)** identical chunks and facts -> **PASSED**.
    - Refinement Routing Determinism: **50/50 (100.0%)** identical fast-path vs refinement routing -> **PASSED**.
  - Separately reported Efficiency & Latency Gates (Trade-offs):
    - Context tokens: **710.9** vs $\le 450.0$ target -> **FAIL**.
    - P50 latency: **5,874.8 ms** vs $\le 4,500.0$ ms target -> **FAIL**.
    - Latency decomposed: initial 32B retrieval median 2,042.7 ms (~34.2%), refinement execution median 398.6 ms (~6.7%), remote NIM synthesis median 3,027.7 ms (~50.7%).
  - Artifacts produced: `data/hybrid_repeatability_results.json`, `data/hybrid_repeatability_report.md`, `data/hybrid_repeatability_run2_audit.jsonl`, `data/hybrid_repeatability_run3_audit.jsonl`.
  - Architecture status: **Qualified Research Champion / Candidate Architecture with Quantified Generator Variance and Explicit Efficiency Trade-off**.

## Phase 35 — Engineering Portfolio & Documentation Standardization
- [x] Step 35A: Freeze winning candidate architecture (`scripts/langgraph_evidence_refinement.py`, ADR 068, ADR 069):
  - Preserved Phase 32B `RetrievalCoordinator` in `src/router/` as the primary engine with zero modifications to `src/`.
  - Enriched `scripts/langgraph_evidence_refinement.py` with deep step-by-step explanatory comments on heuristic zero-LLM gap detection, bounded 1-pass execution, budget caps ($\le 3$ facts, $\le 2$ chunks), and citation provenance invariants.
  - Verified syntax, imports, and live execution.
- [x] Step 35B: Execute and verify full test baseline:
  - Core test suite: 147 / 147 passed in 92.91s (`pytest tests/ -q`).
  - Evaluation harness suite: 244 / 244 passed (`pytest evalkit/tests -q`).
  - Smoke test: LangGraph 9-node execution verified (`scripts/test_langgraph_smoke.py`).
  - Containers: Neo4j and PostgreSQL healthy (`docker ps`).
  - API daemon: Live server running at `http://127.0.0.1:8000`.
- [x] Step 35C: Standardize `README.md` for portfolio presentation:
  - Formulated problem statement and target enterprise/research user personas.
  - Provided plain-English definition of dual-store GraphRAG.
  - Integrated Mermaid request flow diagram covering both core engine and bounded refinement candidate.
  - Published honest 3-run repeatability benchmark comparison against Phase 33D champion and plain vector baseline.
  - Explicitly declared latency and context-token budget trade-offs; decomposed remote cloud latency.
  - Detailed clean installation, setup without secrets, offline test commands, and exact reproduction commands.
- [x] Step 35D: Synchronize canonical documentation:
  - Updated `Docs/ARCHITECTURE.md` with complete dual-store topology and bounded LangGraph refinement.
  - Updated `Docs/FLOWS.md` with Sequence Diagram 7 illustrating the selective refinement flow.
  - Recorded ADR 069 in `Docs/DECISIONS.md`.
  - Updated `Docs/TASKS.md` and `Docs/CODEBASE_MAP.md`.

## Phase 36 — Production Application Integration of Bounded LangGraph Evidence Refinement (ADR 070)
- [x] Step 36A: Pre-implementation Architecture & Boundary Inspection:
  - Inspected existing application architecture in `src/`, candidate script in `scripts/`, test suite, and benchmark artifacts.
  - Formulated clean integration boundary under `src/router/refiner.py` composed into `src/router/coordinator.py`.
  - Verified dependency requirements: added `langgraph>=0.2.0` to `requirements.txt` and `pyproject.toml`.
  - Added explicit configuration toggles (`enable_evidence_refinement`, `max_refined_facts`, `max_refined_chunks`) to `src/core/config.py`.
- [x] Step 36B: Implement Application Evidence Refiner:
  - Created [`src/router/refiner.py`](../src/router/refiner.py) containing `RefinementState` and `EvidenceRefiner`.
  - Integrated zero-overhead heuristic gap detector (`detect_evidence_gap`), bounded 3-node StateGraph (`isolate_gap_node` -> `targeted_retrieval_node` -> `merge_evidence_node`), strict budget caps ($\le 3$ facts, $\le 2$ chunks), and citation provenance extraction.
  - Integrated into [`src/router/coordinator.py`](../src/router/coordinator.py) in Step 3f with try/except fallback to unrefined context on external model/DB errors.
  - Enriched [`src/router/models.py`](../src/router/models.py) with refinement telemetry fields on `RetrievalContext`.
  - Refactored [`scripts/langgraph_evidence_refinement.py`](../scripts/langgraph_evidence_refinement.py) to re-export and wrap the application refiner, eliminating code duplication while preserving script backward compatibility.
- [x] Step 36C: Add Unit & Integration Tests:
  - Created [`tests/test_evidence_refinement.py`](../tests/test_evidence_refinement.py) covering gap detection, fast-path bypass, budget caps, deduplication, coordinator integration, and exception fallback.
  - Verified all 9 new tests pass in 4.00s.
  - Verified full test suite passes with 0 regressions: 156 / 156 passed in 70.07s (`pytest tests/ -q`).
- [x] Step 36D: Live Server & Benchmark Verification:
  - Tested live FastAPI `/query` endpoint across in-scope and out-of-scope queries (100% grounded, 0 invalid citations, correct abstention).
  - Executed benchmark parity check across all 5 hop tiers (`scripts/run_evidence_refinement_benchmark.py --per-hop 1`): achieved 1.00 mean fact score, 100% OOS abstention, 0.0% invalid citations, confirming exact parity with the candidate research champion.
- [x] Step 36E: Canonical Documentation Synchronization:
  - Recorded ADR 070 in [`Docs/DECISIONS.md`](DECISIONS.md).
  - Updated [`Docs/ARCHITECTURE.md`](ARCHITECTURE.md) and [`Docs/FLOWS.md`](FLOWS.md) to reflect `src/router/refiner.py`.
  - Updated [`Docs/CODEBASE_MAP.md`](CODEBASE_MAP.md) inventory and [`README.md`](../README.md).

