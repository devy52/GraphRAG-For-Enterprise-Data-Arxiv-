# GraphRAG 3-Way Evaluation: Evalkit vs Ragas vs DeepEval

Generated: `2026-10-06T03:09:45.657723+00:00`
Snapshot: `data\eval_framework_snapshot.jsonl`
Snapshot SHA-256: `ff5c62fa822cd62c0569ac8d30bc2a52f41cb990b416e56cd2da3530e5996dde`
Questions: **5**

> The same frozen GraphRAG outputs, retrieval contexts, references, and metadata were supplied to all three frameworks. Score differences are evaluator disagreement, not a truth/calibration error.

## Aggregate common metrics

| Metric | Evalkit | Ragas | DeepEval |
|---|---:|---:|---:|
| `faithfulness` | 1.0000 (5/5) | 0.6433 (5/5) | 0.9000 (5/5) |
| `answer_relevancy` | 0.4000 (5/5) | 0.3916 (5/5) | 0.2150 (5/5) |
| `context_precision` | 0.4600 (5/5) | 0.5000 (4/5) | 0.7500 (4/5) |
| `context_recall` | 0.0600 (5/5) | 0.3000 (5/5) | 0.6422 (5/5) |

## Per-question comparison

| ID | Tier | Evalkit faith. | Ragas faith. | DeepEval faith. | Evalkit rel. | Ragas rel. | DeepEval rel. |
|---|---|---:|---:|---:|---:|---:|---:|
| `q_1hop_01` | 1-hop | 1.000 | 0.333 | 1.000 | 1.000 | 0.000 | 0.250 |
| `q_2hop_01` | 2-hop | 1.000 | 0.750 | 1.000 | 1.000 | 0.000 | 0.500 |
| `q_3hop_01` | 3-hop | 1.000 | 0.333 | 0.500 | 0.000 | 0.000 | 0.000 |
| `q_agg_01` | aggregation | 1.000 | 1.000 | 1.000 | 0.000 | 0.958 | 0.200 |
| `q_oos_01` | out-of-scope | 1.000 | 0.800 | 1.000 | 0.000 | 1.000 | 0.125 |

## Important interpretation rules

1. Faithfulness / groundedness is not factual truth.
2. Answer relevancy is not answer completeness or correctness.
3. Context precision/recall depend on how references and contexts are represented.
4. DeepEval custom-model JSON failures are recorded as `null`/error rather than converted to zero.
5. The snapshot is the reproducibility boundary: rerunning a framework without re-running GraphRAG is allowed; silently re-querying GraphRAG is not.
