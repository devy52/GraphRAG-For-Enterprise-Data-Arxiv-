# Phase 30B Evaluation Report: Concise Relational Serialization & De-bloating

Generated: `2026-10-06T12:42:15.376167+00:00`  
Dataset SHA-256: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
Pipeline Under Test: **Hybrid GraphRAG + Precedence + Canonical Resolver + Concise Relational Formatter** (ADR 055: memory=OFF, Qwen2.5-7B-Instruct)  

## 1. High-Level Performance Comparison: Run 1 vs. Run 2 vs. Run 3A vs. Run 3B vs. Phase 30 vs. Phase 30B

| Metric | Run 1 (Baseline) | Run 2 (Metadata) | Run 3A (Precedence) | Run 3B (Canonical ID) | Phase 30 (Verbose Paths) | Phase 30B (Concise Relations) | Delta (30B vs. 3B) | Delta (30B vs. 30) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Fact Score (Overall 50Q)** | 0.6750 | 0.6458 | 0.7458 | 0.7583 | 0.7417 | **0.7500** | **-0.0083** | **+0.0083** |
| **Strict Success Rate** | 42.5% | 40.0% | 60.0% | 60.0% | 52.5% | **55.0%** | **-5.0%** | **+2.5%** |
| **Unified Evidence Recall** | 0.5500 | 0.5958 | 0.5958 | 0.6708 | 0.6708 | **0.6708** | +0.0000 | +0.0000 |
| **Graph Recall** | 0.5000 | 0.5000 | 0.4744 | 0.5897 | 0.5897 | **0.5897** | +0.0000 | +0.0000 |
| **Metadata Recall** | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | **1.0000** | 0.0000 | 0.0000 |
| **Abstention Accuracy** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |
| **Context Tokens (Mean)** | 448.6 | 467.4 | 458.2 | 392.2 | 526.3 | **392.3** | +0.1 | -134.0 |
| **Latency p50** | 4188.0 ms | 5693.3 ms | 3778.3 ms | 4115.6 ms | 4300.2 ms | 4217.2 ms | +101.6 ms | -83.0 ms |

## 2. Targeted Stratified Slice Analysis

### 2.1 Multi-Hop Reasoning Slice (2-Hop, 3-Hop, Aggregation, N=30)
Measures whether concise directional serialization resolves multi-hop synthesis without token bloat.

| Metric | Run 3B | Phase 30 (Verbose) | Phase 30B (Concise) | Delta (30B vs. 3B) | Delta (30B vs. 30) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-Hop Fact Score Mean** | 0.7444 | 0.7556 | **0.7500** | **+0.0056** | **-0.0056** |
| **Multi-Hop Unified Recall Mean** | 0.6944 | 0.6944 | **0.6944** | +0.0000 | 0.0000 |
| **Type-C Multi-Hop Failures (< 1.0 fact)** | 14/30 | 15/30 | **15/30** | **+1** | **+0** |

### 2.2 Single-Hop Invariant Verification (1-Hop, N=10)
Validates whether removing boilerplate restores single-hop fact accuracy.

| Metric | Run 3B | Phase 30 (Verbose) | Phase 30B (Concise) | Delta (30B vs. 3B) | Delta (30B vs. 30) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Single-Hop Fact Score Mean** | 0.8000 | 0.7000 | **0.7500** | -0.0500 | +0.0500 |

## 3. Notable Per-Question Shifts vs. Run 3B

| Question ID | Hop Type | Run 3B Fact | Phase 30B Fact | Delta | Generated Answer (Phase 30B) |
|---|---|:---:|:---:|:---:|---|
| `q_1hop_10` | 1-hop | 1.0000 | **0.5000** | -0.5000 | RAGU is a multi-step GraphRAG engine. It incorporates the Meno-Lite-0.1 model architecture, a 7B model optimized for lan... |
| `q_2hop_03` | 2-hop | 0.0000 | **0.5000** | +0.5000 | Unfortunately, the provided context does not contain sufficient information to answer the question about the three agent... |
| `q_3hop_01` | 3-hop | 1.0000 | **0.6667** | -0.3333 | GraphRAG-R1's reinforcement learning framework enforces constraints on graph traversal during generation by adopting a p... |
| `q_agg_02` | aggregation | 0.5000 | **1.0000** | +0.5000 | There is insufficient evidence in the provided context to identify shared limitations of vanilla RAG that are mentioned ... |
| `q_agg_05` | aggregation | 1.0000 | **0.5000** | -0.5000 | There is insufficient evidence to compare the scope of evaluation in 'RAG vs. GraphRAG' and 'Do We Still Need GraphRAG?'... |
| `q_agg_06` | aggregation | 0.5000 | **1.0000** | +0.5000 | The context optimization approaches proposed by ACE-GraphRAG include gap-aware refinement, retrieval branches, and task-... |
| `q_agg_10` | aggregation | 1.0000 | **0.5000** | -0.5000 | There is insufficient evidence to compare the reinforcement learning formulations used in GraphRAG-R1 and MetaRAG, as th... |

## 4. Acceptance Criteria Verification Summary

1. **Strict Success Rate**: 60.0% -> **55.0%** (Target: >= 60.0%)
2. **Overall Fact Score**: 0.7583 -> **0.7500** (Target: >= 0.7583)
3. **Single-Hop Fact Score**: 0.8000 -> **0.7500** (Target: >= 0.8000)
4. **Type-C Multi-Hop Failures**: 14 -> **15** (Target: <= 14)
5. **Mean Context Tokens**: 392.2 -> **392.3** (Target: <= 392.2 tokens)
6. **Unified Evidence Recall**: 0.6708 -> **0.6708** (Target: >= 0.6708)
7. **Provenance Validity**: Individual `[chunk: {c}]` tags strictly preserved and resolved.
8. **Frozen Invariants**: CanonicalEntityResolver, MetadataResolver, Precedence Suppression, EvaluatorV2, gold dataset, and session isolation remained 100% frozen.
