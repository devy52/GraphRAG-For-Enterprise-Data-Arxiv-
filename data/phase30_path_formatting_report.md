# Phase 30 Evaluation Report: Relational Traversal Path & Graph Fact Statement Formatting

Generated: `2026-10-06T11:07:41.511455+00:00`  
Dataset SHA-256: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
Pipeline Under Test: **Hybrid GraphRAG + Precedence + Canonical Resolver + Relational Path Formatter** (ADR 054: memory=OFF, Qwen2.5-7B-Instruct)  

## 1. High-Level Performance Comparison: Run 1 vs. Run 2 vs. Run 3A vs. Run 3B vs. Phase 30

| Metric | Run 1 (Baseline Hybrid) | Run 2 (Unfiltered Metadata) | Run 3A (Precedence Filter) | Run 3B (Canonical Entity Resolution) | Phase 30 (Relational Path Formatting) | Delta (P30 vs. 3B) | Delta (P30 vs. 1) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Fact Score (Overall 50Q)** | 0.6750 | 0.6458 | 0.7458 | 0.7583 | **0.7417** | **-0.0166** | **+0.0667** |
| **Strict Success Rate** | 42.5% | 40.0% | 60.0% | 60.0% | **52.5%** | **-7.5%** | **+10.0%** |
| **Unified Evidence Recall** | 0.5500 | 0.5958 | 0.5958 | 0.6708 | **0.6708** | +0.0000 | **+0.1208** |
| **Graph Recall** | 0.5000 | 0.5000 | 0.4744 | 0.5897 | **0.5897** | +0.0000 | +0.0897 |
| **Metadata Recall** | 0.0000 | 1.0000 | 1.0000 | 1.0000 | **1.0000** | 0.0000 | **+1.0000** |
| **Abstention Accuracy** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |
| **Context Tokens (Mean)** | 448.6 | 467.4 | 458.2 | 392.2 | 526.3 | +134.1 | +77.7 |
| **Latency p50** | 4188.0 ms | 5693.3 ms | 3778.3 ms | 4115.6 ms | 4300.2 ms | +184.6 ms | +112.2 ms |

## 2. Targeted Stratified Slice Analysis

### 2.1 Multi-Hop Reasoning Slice (2-Hop, 3-Hop, Aggregation, N=30)
Measures whether explicit relational path formatting resolves Type-C multi-hop synthesis bottlenecks.

| Metric | Run 3B | Phase 30 | Delta (P30 vs. 3B) |
|---|:---:|:---:|:---:|
| **Multi-Hop Fact Score Mean** | 0.7444 | **0.7556** | **+0.0112** |
| **Multi-Hop Unified Recall Mean** | 0.6944 | **0.6944** | +0.0000 |
| **Type-C Multi-Hop Failures (< 1.0 fact)** | 14/30 | **15/30** | **+1** |

### 2.2 Single-Hop Invariant Verification (1-Hop, N=10)
Validates that relational path formatting does not introduce regressions on single-hop queries.

| Metric | Run 3B | Phase 30 | Delta (P30 vs. 3B) |
|---|:---:|:---:|:---:|
| **Single-Hop Fact Score Mean** | 0.8000 | **0.7000** | -0.1000 |

## 3. Per-Question Impact on Notable Multi-Hop Cases

| Question ID | Hop Type | Run 3B Fact | Phase 30 Fact | Delta | Generated Answer (Phase 30) |
|---|---|:---:|:---:|:---:|---|
| `q_2hop_03` | 2-hop | 0.0000 | **0.5000** | +0.5000 | Unfortunately, the provided context does not contain sufficient information to answer the question about the three agent... |
| `q_2hop_04` | 2-hop | 1.0000 | **0.5000** | -0.5000 | The HeRo framework targets mobile devices for adaptive agentic RAG orchestration. This is supported by the fact that exp... |
| `q_3hop_03` | 3-hop | 0.3333 | **0.6667** | +0.3334 | Unfortunately, the provided context does not contain sufficient information to answer the question about how Dissecting ... |
| `q_agg_02` | aggregation | 0.5000 | **1.0000** | +0.5000 | There is insufficient evidence in the provided context to identify the shared limitations of vanilla RAG that are mentio... |
| `q_agg_10` | aggregation | 1.0000 | **0.5000** | -0.5000 | There is insufficient evidence to compare the reinforcement learning formulations used in GraphRAG-R1 and MetaRAG. The p... |

## 4. Acceptance Criteria Verification Summary

1. **Multi-Hop Fact Score**: 0.7444 -> **0.7556** (+0.0112)
2. **Strict Success Rate**: 60.0% -> **52.5%** (-7.5%)
3. **Non-Multi-Hop Fact Score**: 0.8000 -> **0.7000** (-0.1000)
4. **Unified Recall Stability**: 0.6708 -> **0.6708** (Target: ≥0.6708)
5. **Context Size Boundedness**: 392.2 -> **526.3** tokens (+134.1 tokens)
6. **Type-C Multi-Hop Failure Count**: 14 -> **15** failures
7. **Frozen Invariants**: CanonicalEntityResolver, MetadataResolver, Precedence Suppression, EvaluatorV2, gold dataset, and session isolation remained 100% frozen.
