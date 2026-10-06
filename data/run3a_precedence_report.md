# Run 3A Evaluation Report: Evidence Precedence & Conflict Suppression

Generated: `2026-10-06T09:42:03.930236+00:00`  
Dataset SHA-256: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
Pipeline Under Test: **Hybrid GraphRAG + Precedence Resolver** (ADR 052: memory=OFF, Qwen2.5-7B-Instruct)  

## 1. High-Level Performance Comparison: Run 1 vs. Run 2 vs. Run 3A

| Metric | Run 1 (Baseline Hybrid) | Run 2 (Unfiltered Metadata) | Run 3A (Precedence & Suppressed) | Delta (Run 3A vs. Run 1) |
|---|:---:|:---:|:---:|:---:|
| **Metadata Recall** | 0.0000 | 1.0000 | 1.0000 | **+1.0000** |
| **Unified Evidence Recall** | 0.5500 | 0.5958 | 0.5958 | **+0.0458** |
| **Chunk Recall** | 0.2821 | 0.2821 | 0.2821 | +0.0000 |
| **Graph Recall** | 0.5000 | 0.5000 | 0.4744 | -0.0256 |
| **Fact Score (Overall 50Q)** | 0.6750 | 0.6458 | **0.7458** | **+0.0708** |
| **Strict Success Rate** | 42.5% | 40.0% | **60.0%** | **+17.5%** |
| **Abstention Accuracy** | 100.0% | 100.0% | 100.0% | 0.0% |
| **Context Tokens (Mean)** | 448.6 | 467.4 | 458.2 | +9.6 |
| **Latency p50** | 4188.0 ms | 5693.3 ms | 3778.3 ms | -409.7 ms |

## 2. Stratified Slice Analysis

### 2.1 Metadata-Dependent Questions (N=3)
Targets: `q_1hop_01` (Authors of GraphRAG-R1), `q_1hop_04` (Author of Dissecting Agentic RAG), `q_agg_04` (Kotoge et al. efficiency strategy).

| Metric | Run 1 | Run 2 | Run 3A | Delta (3A vs 1) |
|---|:---:|:---:|:---:|:---:|
| **Metadata Recall** | 0.0000 | 1.0000 | 1.0000 | **+1.0000** |
| **Fact Score** | 0.3333 | 0.6667 | **1.0000** | **+0.6667** |

| Question ID | Question | Run 1 Fact | Run 2 Fact | Run 3A Fact | Generated Answer (Run 3A) |
|---|---|:---:|:---:|:---:|---|
| `q_1hop_01` | Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning? | 0.0000 | 1.0000 | **1.0000** | The primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning are Chuanyue Yu, Kuo Z... |
| `q_1hop_04` | Who authored the component ablation study 'Dissecting Agentic RAG' for multi-hop QA? | 0.5000 | 0.0000 | **1.0000** | The authors of the component ablation study 'Dissecting Agentic RAG' for multi-hop QA are Sheroz Shaikh [meta_arxiv_2606... |
| `q_agg_04` | Compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware. | 0.5000 | 1.0000 | **1.0000** | There is insufficient evidence in the provided context to directly compare the efficiency strategies of HeRo and Kotoge ... |

### 2.2 Non-Metadata Answerable Questions (N=37)
Validates that tightening the metadata trigger prevents regression on non-metadata queries.

| Metric | Run 1 | Run 2 | Run 3A | Delta (3A vs 1) | Delta (3A vs 2) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Fact Score Mean** | 0.7027 | 0.6441 | **0.7252** | +0.0225 | **+0.0811** |

## 3. Auditable Suppression Ledger (ADR 052 Provenance Tracking)

| Question ID | Reason | Source ID | Authoritative Source ID | Suppressed Fact |
|---|---|---|---|---|
| `q_1hop_04` | `placeholder_conflict` | `chunk_arxiv_2606_21553v1_000` | `meta_arxiv_2606_21553v1_authors` | Paper 'Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model' was authored by Unknown Author [chunk: chunk_arxiv_2606_21553v1_000]. |
| `q_2hop_03` | `placeholder_conflict` | `chunk_arxiv_2606_21553v1_000` | `meta_arxiv_2606_21553v1_authors` | Entity 'Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model' -[:AUTHORED_BY]- 'Unknown Author' (Author) [chunk: chunk_arxiv_2606_21553v1_000]. |

## 4. Key Findings & Acceptance Verification

1. **`q_1hop_04` Conflict Recovery**: Successfully suppressed conflicting 'Unknown Author' fact in favor of authoritative catalog header. Context contained Sheroz Shaikh only; fact score recovered to **1.0000**.
2. **`q_2hop_02` Incidental Trigger Fix**: `metadata intent = False` produced no catalog header. Fact score was **1.0000**.
3. **Non-Metadata Slice Recovery**: Non-metadata fact score moved from 0.6441 in Run 2 to **0.7252** in Run 3A.
4. **Complete Traceability**: All suppressed evidence was recorded in the audit trail without silently hiding retrieval defects.
5. **Invariants Preserved**: Cypher templates, graph queries, and format_records_to_statements remained 100% frozen.
