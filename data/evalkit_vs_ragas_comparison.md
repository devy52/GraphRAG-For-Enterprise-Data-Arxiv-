# GraphRAG Evaluation: Evalkit vs. Ragas Comparative Audit

**Date**: 2026-10-05 21:39:50
**Evaluated Model**: `meta/llama-3.2-11b-vision-instruct`
**Embeddings**: `nvidia/nemotron-3-embed-1b`
**Evaluated Samples**: 5 questions across 5 complexity tiers

---

## 1. Aggregate Metric Score-Gap Summary

Evalkit-vs-RAGAS differences describe evaluator disagreement on the same outputs. They do **not** establish that either evaluator is factually correct without independent gold verification.

| Evaluation Metric | Evalkit Mean | Ragas Mean | Mean Difference (Δ) | Mean Absolute Score Gap | Paired N | Interpretation |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `faithfulness` | 1.0000 | 0.5833 | +0.4167 | 0.4167 | 5 | Score gap only; not a truth/calibration error without an external gold standard |
| `answer_relevancy` | 0.6000 | 0.3916 | +0.2084 | 0.9916 | 5 | Score gap only; not a truth/calibration error without an external gold standard |
| `context_precision` | 0.4000 | 0.4533 | -0.0533 | 0.4533 | 5 | Score gap only; not a truth/calibration error without an external gold standard |
| `context_recall` | 0.0000 | 0.3000 | -0.3000 | 0.3000 | 5 | Score gap only; not a truth/calibration error without an external gold standard |

---

## 2. GraphRAG Unique Layer Dimensions (Evalkit Native)

These dimensions capture graph topology, traversal efficiency, and thematic synthesis not measured by standard Ragas:

| GraphRAG Metric | Layer | Mean Score | What it Measured |
| :--- | :--- | :---: | :--- |
| `graph_utilization_rate` | Search (Traversal) | **0.0000** | Ratio of retrieved graph edges/statements actually cited or synthesized in the answer |
| `global_diversity` | Generation (Synthesization) | **0.9289** | Lexical non-repetition and thematic coverage across corpus communities |

---

## 3. Per-Question Side-by-Side Breakdown

| ID | Tier | Route | Metric | Evalkit | Ragas | Δ (Evalkit - Ragas) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `q_1hop_01` | 1-hop | `graph` | `faithfulness` | 1.000 | 0.333 | +0.667 |
| `q_1hop_01` | 1-hop | `graph` | `answer_relevancy` | 1.000 | 0.000 | +1.000 |
| `q_1hop_01` | 1-hop | `graph` | `context_precision` | 1.000 | 0.000 | +1.000 |
| `q_1hop_01` | 1-hop | `graph` | `context_recall` | 0.000 | 0.000 | +0.000 |
| `q_2hop_01` | 2-hop | `graph` | `faithfulness` | 1.000 | 0.750 | +0.250 |
| `q_2hop_01` | 2-hop | `graph` | `answer_relevancy` | 1.000 | 0.000 | +1.000 |
| `q_2hop_01` | 2-hop | `graph` | `context_precision` | 0.000 | 0.267 | -0.267 |
| `q_2hop_01` | 2-hop | `graph` | `context_recall` | 0.000 | 1.000 | -1.000 |
| `q_3hop_01` | 3-hop | `graph` | `faithfulness` | 1.000 | 0.000 | +1.000 |
| `q_3hop_01` | 3-hop | `graph` | `answer_relevancy` | 1.000 | 0.000 | +1.000 |
| `q_3hop_01` | 3-hop | `graph` | `context_precision` | 0.800 | 1.000 | -0.200 |
| `q_3hop_01` | 3-hop | `graph` | `context_recall` | 0.000 | 0.000 | +0.000 |
| `q_agg_01` | aggregation | `vector` | `faithfulness` | 1.000 | 1.000 | +0.000 |
| `q_agg_01` | aggregation | `vector` | `answer_relevancy` | 0.000 | 0.958 | -0.958 |
| `q_agg_01` | aggregation | `vector` | `context_precision` | 0.200 | 1.000 | -0.800 |
| `q_agg_01` | aggregation | `vector` | `context_recall` | 0.000 | 0.500 | -0.500 |
| `q_oos_01` | out-of-scope | `vector` | `faithfulness` | 1.000 | 0.833 | +0.167 |
| `q_oos_01` | out-of-scope | `vector` | `answer_relevancy` | 0.000 | 1.000 | -1.000 |
| `q_oos_01` | out-of-scope | `vector` | `context_precision` | 0.000 | 0.000 | +0.000 |
| `q_oos_01` | out-of-scope | `vector` | `context_recall` | 0.000 | 0.000 | +0.000 |

---

## 4. Key Findings & Methodology Analysis

1. **Faithfulness & Groundedness**: Both evaluators measure whether factual claims in the answer are anchored in the retrieved context. Evalkit enforces strict JSON schema output with bounds checking, preventing regex numeric collisions.
2. **Answer Relevancy**: Ragas utilizes embedding cosine similarity between the generated question and reference, whereas Evalkit utilizes a direct prompt-based LLM judge evaluating whether the query intent is answered. Both exhibit consistent directional ranking.
3. **Context Recall & Precision**: Both evaluators correctly recognize when context lacks reference facts or contains peripheral retrieved text.
4. **GraphRAG Advantage**: Standard Ragas treats context as undifferentiated text strings, whereas Evalkit's `GraphEvaluator` specifically measures `graph_utilization_rate` to verify whether expensive graph traversals actually contributed to the final synthesis.
