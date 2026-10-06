# Evaluation V2 Fixes Applied

This bundle contains the Evaluation V2 integrity fixes requested during the benchmark audit.

## Fixed

1. Retrieval metrics now return `N/A`/`None` when gold retrieval labels are unavailable instead of manufacturing perfect recall/MRR.
2. The V2 dataset is validated before a benchmark run: 50 questions, 40 answerable, 10 out-of-scope, required facts present, and all answerable gold chunk IDs must exist in the corpus.
3. Benchmark runs record a SHA-256 fingerprint of the exact dataset used. Per-question records also preserve that fingerprint.
4. V2 retrieval/synthesis failure paths fail closed. They no longer inject `reference_answer`, expected keywords, or synthetic evidence into model context.
5. Fact evaluation now separates answerable factual coverage from abstention scoring. Unanswerable questions receive `fact_score = N/A` rather than factual credit.
6. Explicit fact contradictions are detected conservatively and reported separately from missing facts.
7. Graph provenance chunk IDs can be supplied as valid evidence IDs for citation validation.
8. The ambiguous `abstention_correct` meaning was corrected; `did_not_abstain` is now separate and the old field means only a correctly classified abstention.
9. Groundedness reports its method explicitly: `llm_judge`, `lexical_overlap_heuristic`, `no_context`, or deterministic refusal.
10. The Eval V2 package uses lazy imports so deterministic evaluator tests can run without optional LLM runtime packages such as `openai`.
11. The Evalkit-vs-RAGAS comparison no longer converts missing/NaN scores to zero or labels score disagreement as truth-calibration error. It reports paired finite-score gaps instead.
12. The legacy benchmark's offline retrieval fallbacks no longer inject benchmark facts into model context.
13. Historical pre-fix V2 result artifacts are explicitly marked `STALE_UNTRUSTED_PRE_FIX` and must not be cited as current benchmark results.

## Validation performed in this environment

- `pytest -q tests/test_eval_v2.py tests/test_benchmark_integrity.py` → **17 passed**
- `python -m compileall -q src scripts tests` → **PASS**
- `python scripts/validate_benchmark_v2_dataset.py` → **PASS**
- `python scripts/audit_eval_v2.py` → **PASS**

## Important limitation

The full live 50-question benchmark was not rerun in this environment because the uploaded project runtime lacks the `openai` and `ragas` dependencies and the live GraphRAG services/credentials are not available here. Therefore the stored pre-fix benchmark numbers remain historical; run `python scripts/run_benchmark_v2.py` in the real project environment to generate fresh, provenance-fingerprinted results.
