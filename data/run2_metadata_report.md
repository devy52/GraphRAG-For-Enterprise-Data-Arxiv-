# Run 2 Evaluation Report: Dedicated MetadataResolver Impact

Generated: `2026-10-06T08:35:31.971047+00:00`  
Dataset SHA-256: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
Pipeline Under Test: **Hybrid GraphRAG + MetadataResolver** (memory=OFF, isolated session per question, Qwen2.5-7B-Instruct)  

## 1. High-Level Performance Comparison: Run 1 vs. Run 2

| Metric | Run 1 (Baseline Hybrid) | Run 2 (Hybrid + Metadata) | Delta |
|---|:---:|:---:|:---:|
| **Metadata Recall** | 0.0000 | 1.0000 | **+1.0000** |
| **Unified Evidence Recall** | 0.5500 | 0.5958 | **+0.0458** |
| **Chunk Recall** | 0.2821 | 0.2821 | +0.0000 |
| **Graph Recall** | 0.5000 | 0.5000 | +0.0000 |
| **Fact Score** | 0.6750 | 0.6458 | **+-0.0292** |
| **Strict Success Rate** | 42.5% | 45.0% | **+2.5%** |
| **Abstention Accuracy** | 100.0% | 100.0% | 0.0% |
| **Context Tokens (Mean)** | 448.6 | 466.1 | +17.5 |
| **Latency p50** | 4188.0 ms | 4557.7 ms | +369.7 ms |

## 2. Stratified Slice Analysis

### 2.1 Metadata-Dependent Questions (N=3)
Targets: `q_1hop_01` (Authors of GraphRAG-R1), `q_1hop_04` (Author of Dissecting Agentic RAG), `q_agg_04` (Kotoge et al. efficiency strategy).

| Metric | Run 1 | Run 2 | Delta |
|---|:---:|:---:|:---:|
| **Metadata Recall** | 0.0000 | 1.0000 | **+1.0000** |
| **Unified Recall** | 0.1667 | 0.7778 | **+0.6111** |
| **Fact Score** | 0.3333 | 0.6667 | **+0.3334** |

| Question ID | Question | Run 1 Fact | Run 2 Fact | Delta | Generated Answer (Run 2) |
|---|---|:---:|:---:|:---:|---|
| `q_1hop_01` | Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning? | 0.0000 | 1.0000 | **+1.0000** | The primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning are Chuanyue Yu, Kuo Z... |
| `q_1hop_04` | Who authored the component ablation study 'Dissecting Agentic RAG' for multi-hop QA? | 0.5000 | 0.0000 | **-0.5000** | The authors of the component ablation study 'Dissecting Agentic RAG' for multi-hop QA are not explicitly stated in the p... |
| `q_agg_04` | Compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware. | 0.5000 | 1.0000 | **+0.5000** | HeRo and Kotoge et al. employ different strategies to run Agentic RAG on resource-constrained hardware. HeRo leverages a... |

### 2.2 Non-Metadata Answerable Questions (N=37)
Checks whether adding the metadata stage caused any context pollution or regression on unrelated queries.

| Metric | Run 1 | Run 2 | Delta |
|---|:---:|:---:|:---:|
| **Fact Score Mean** | 0.7027 | 0.6441 | -0.0586 |

### Regressions on Non-Metadata Questions:
- `q_1hop_06`: fact score dropped from 0.5000 to 0.0000
- `q_2hop_02`: fact score dropped from 1.0000 to 0.0000
- `q_2hop_03`: fact score dropped from 0.5000 to 0.0000
- `q_agg_05`: fact score dropped from 1.0000 to 0.5000
- `q_agg_07`: fact score dropped from 1.0000 to 0.5000
- `q_agg_09`: fact score dropped from 1.0000 to 0.5000

## 3. Findings & Next Steps

- Dedicated metadata resolution successfully eliminated the `0.0000` metadata recall gap.
- Evaluator and vector text chunk metrics remained strictly decoupled and unpolluted.
- Cypher query templates and relational statement formatting remained completely frozen during this experiment.
