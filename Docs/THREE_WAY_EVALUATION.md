# Three-Way Evaluation & Browser Evidence

## Purpose

This project now has a reproducible evaluation path that evaluates **the same frozen GraphRAG outputs** with Evalkit, Ragas, and DeepEval. The application is queried once during snapshot capture; evaluators never re-query the GraphRAG system. This is required for a meaningful evaluator comparison because otherwise stochastic generation, routing, retrieval, or cache effects can be mistaken for evaluator disagreement.

## Frameworks

Common metrics are compared where semantics overlap:

- Evalkit: faithfulness, answer relevancy, context precision, context recall, plus GraphRAG-specific graph utilization and global diversity.
- Ragas: faithfulness, answer relevancy, context precision, context recall.
- DeepEval: `FaithfulnessMetric`, `AnswerRelevancyMetric`, `ContextualPrecisionMetric`, and `ContextualRecallMetric`, using the project OpenAI-compatible/NVIDIA NIM endpoint.

Ragas context recall uses the reference as a proxy for relevant reference information; this means it is reference-dependent rather than a pure ID-level retrieval metric. Ragas answer relevancy measures relevance to the user input and should not be interpreted as factual correctness.

DeepEval's faithfulness evaluates whether the generated output is aligned with retrieval context, and its answer relevancy and contextual precision/recall are likewise LLM-as-judge measures.

## Installation

The project keeps evaluation dependencies out of the production requirements:

```bash
pip install -r requirements-evaluation.txt
playwright install chromium
```

The bundle pins Ragas to 0.4.3 and DeepEval to 4.0.7 for reproducibility. Ragas 0.4.3 is currently the package release recorded on PyPI for the project.

## Frozen snapshot workflow

```bash
python scripts/compare_evalkit_ragas_deepeval.py --capture-only --per-hop 1
python scripts/compare_evalkit_ragas_deepeval.py --evaluate-only
```

The snapshot is the reproducibility boundary. It stores the question, answer, retrieval context, reference, required facts, gold chunk IDs, route metadata, and latency. Gold labels are never inserted into the runtime retrieval context.

## Plain Vector vs Hybrid

```bash
python scripts/compare_plain_vector_hybrid.py --per-hop 1
```

This executes both real systems on the same stratified questions. It is separate from the three-framework evaluator comparison.

## Browser evidence

The production UI has a guarded test-only header override. Keep the setting disabled in production:

```text
ENABLE_EVAL_MODE_OVERRIDE=false
```

For a controlled local evaluation session, set it to `true`, start FastAPI, then run:

```bash
python scripts/browser_compare_plain_hybrid.py --base-url http://127.0.0.1:8000
```

The browser runner disables the UI response cache to prevent the second mode from reusing the first mode's answer. It records WebM video and WebP screenshots/keyframes. Browser artifacts are observational evidence only and are never fed into the numeric benchmark.

## Interpretation guardrails

A high faithfulness/groundedness score does not prove factual truth. A high answer-relevancy score does not prove completeness. Ragas/DeepEval/Evalkit score gaps are evaluator disagreement, not an externally validated calibration error. Final factual claims still require the authoritative V2 fact-level benchmark and/or independently verified ground truth.
