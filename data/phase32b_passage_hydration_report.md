# Phase 32B Benchmark Report: Multi-Hop Graph-Guided Passage Hydration

**Timestamp**: `2026-10-06T14:39:50.898821+00:00`  
**Dataset SHA-256**: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
**Generator Model**: `Qwen2.5-7B-Instruct` (`temperature=0.0`)  
**Intervention Under Test**: Step 32A Graph Passage Hydration (`enable_graph_passage_hydration=True`, `max_graph_hydrated_passages=3`)  
**Selection Heuristic**: Deterministic graph-evidence selection heuristic (`-frequency_in_traversal`, `first_seen_traversal_index`)  
**Comparison Baseline**: Frozen Run 3B (Channel-Strict Corrected Baseline)  

## 1. Pre-Registered Engineering Gates Evaluation

| Gate / Metric | Frozen Run 3B Baseline | Target Threshold | Measured Step 32B | Delta (32B vs. 3B) | Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Substantive Chunk Recall** | 0.2821 | >= 0.4000 | **0.6538** | 0.3717 | **PASS** |
| **Unified Evidence Recall** | 0.3083 | >= 0.4500 | **0.6708** | 0.3625 | **PASS** |
| **Overall Fact Score** | 0.7583 | >= 0.7800 | **0.8208** | 0.0625 | **PASS** |
| **Strict Success Rate (Answerable)** | 24/40 (60.0%) | >= 27/40 (>= 67.5%) | **28/40 (70.0%)** | +10.0% | **PASS** |
| **Mean Context Tokens** | 392.2 | <= 450.0 | **598.0** | 205.8 | **FAIL** |
| **P50 Latency** | 4115.6 ms | <= 4500.0 ms | **4112.7 ms** | -2.9 ms | **PASS** |
| **Invalid Citation Rate** | 0.0% | 0.0% | **0.0%** | +0.0% | **PASS** |

## 2. Layer-by-Layer Architectural Results

### Layer A: Retrieval Recall (Channel-Strict Accounting)
- **Substantive Document Chunk Recall**: `0.2821` -> **`0.6538`** (+0.3717)
- **Unified Evidence Recall**: `0.3083` -> **`0.6708`** (+0.3625)
- **Authoritative Metadata Recall**: `1.0000` (100% stable)

### Layer B: Answer Quality & Stratified Fact Scores
- **Overall Fact Score (Answerable 40Q)**: `0.7583` -> **`0.8208`** (+0.0625)
- **Strict Success Rate (Score >= 0.70)**: `24/40` (60.0%) -> **`28/40`** (70.0%)

| Stratum | Run 3B Fact Score | Step 32B Fact Score | Delta |
| :--- | :---: | :---: | :---: |
| **1-hop (10Q)** | 0.8000 | **0.7000** | -0.1000 |
| **2-hop (10Q)** | 0.7000 | **0.8000** | +0.1000 |
| **3-hop (10Q)** | 0.7333 | **0.9333** | +0.2000 |
| **aggregation (10Q)** | 0.8000 | **0.8500** | +0.8500 |

### Layer E: Efficiency & Measured Latency
- **Mean Context Tokens**: `392.2` -> **`598.0`** (+205.8 tokens; Target: <= 450.0)
- **End-to-End P50 Latency**: `4115.6 ms` -> **`4112.7 ms`** (-2.9 ms; Target: <= 4500.0 ms)
- **End-to-End P95 Latency**: `36333.8 ms` -> **`31283.2 ms`**
- **Database Hydration Lookup (Indexed Batch)**: p50 = `6.43 ms`, p95 = `12.47 ms` across `40` active queries

### Hydration Budget Audit
- Discovered Candidate Graph Chunk IDs: `177`
- Selected for Hydration: `75`
- Successfully Hydrated from PostgreSQL: `75`
- Omitted due to Budget Cap (<=3): `64`
- Invalid Citation Rate: `0.0%` (0.0% target preserved)

## 3. Question-by-Question Comparison vs Run 3B

| QID | Hop | Run 3B Fact | Step 32B Fact | Delta | Run 3B Chunks | Step 32B Chunks | Hydrated Chunks | Run 3B Tokens | Step 32B Tokens |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `q_1hop_01` | 1-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 579 |
| `q_1hop_02` | 1-hop | 0.0000 | **0.0000** | +0.00 | 2 | 5 | +3 | — | 811 |
| `q_1hop_03` | 1-hop | 0.0000 | **0.0000** | +0.00 | 2 | 5 | +3 | — | 818 |
| `q_1hop_04` | 1-hop | 1.0000 | **1.0000** | +0.00 | 2 | 2 | +0 | — | 376 |
| `q_1hop_05` | 1-hop | 1.0000 | **0.5000** | -0.50 | 2 | 5 | +3 | — | 1035 |
| `q_1hop_06` | 1-hop | 1.0000 | **0.5000** | -0.50 | 2 | 5 | +3 | — | 960 |
| `q_1hop_07` | 1-hop | 1.0000 | **1.0000** | +0.00 | 2 | 2 | +0 | — | 302 |
| `q_1hop_08` | 1-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 536 |
| `q_1hop_09` | 1-hop | 1.0000 | **1.0000** | +0.00 | 1 | 3 | +2 | — | 548 |
| `q_1hop_10` | 1-hop | 1.0000 | **1.0000** | +0.00 | 1 | 2 | +1 | — | 367 |
| `q_2hop_01` | 2-hop | 1.0000 | **1.0000** | +0.00 | 2 | 4 | +2 | — | 621 |
| `q_2hop_02` | 2-hop | 1.0000 | **1.0000** | +0.00 | 2 | 5 | +3 | — | 912 |
| `q_2hop_03` | 2-hop | 0.0000 | **0.0000** | +0.00 | 2 | 2 | +0 | — | 583 |
| `q_2hop_04` | 2-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 391 |
| `q_2hop_05` | 2-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 696 |
| `q_2hop_06` | 2-hop | 0.0000 | **1.0000** | +1.00 | 2 | 5 | +3 | — | 1138 |
| `q_2hop_07` | 2-hop | 0.5000 | **0.5000** | +0.00 | 2 | 5 | +3 | — | 831 |
| `q_2hop_08` | 2-hop | 1.0000 | **1.0000** | +0.00 | 1 | 4 | +3 | — | 829 |
| `q_2hop_09` | 2-hop | 1.0000 | **1.0000** | +0.00 | 2 | 2 | +0 | — | 368 |
| `q_2hop_10` | 2-hop | 0.5000 | **0.5000** | +0.00 | 2 | 3 | +1 | — | 426 |
| `q_3hop_01` | 3-hop | 1.0000 | **1.0000** | +0.00 | 2 | 4 | +2 | — | 682 |
| `q_3hop_02` | 3-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 632 |
| `q_3hop_03` | 3-hop | 0.3333 | **1.0000** | +0.67 | 2 | 4 | +2 | — | 775 |
| `q_3hop_04` | 3-hop | 1.0000 | **1.0000** | +0.00 | 2 | 3 | +1 | — | 464 |
| `q_3hop_05` | 3-hop | 0.6667 | **0.6667** | +0.00 | 2 | 5 | +3 | — | 859 |
| `q_3hop_06` | 3-hop | 0.6667 | **1.0000** | +0.33 | 2 | 5 | +3 | — | 1016 |
| `q_3hop_07` | 3-hop | 1.0000 | **1.0000** | +0.00 | 1 | 2 | +1 | — | 402 |
| `q_3hop_08` | 3-hop | 0.6667 | **0.6667** | +0.00 | 2 | 5 | +3 | — | 900 |
| `q_3hop_09` | 3-hop | 0.3333 | **1.0000** | +0.67 | 5 | 8 | +3 | — | 1196 |
| `q_3hop_10` | 3-hop | 0.6667 | **1.0000** | +0.33 | 2 | 4 | +2 | — | 545 |
| `q_agg_01` | aggregation | 0.5000 | **1.0000** | +0.50 | 3 | 3 | +0 | — | 513 |
| `q_agg_02` | aggregation | 0.5000 | **1.0000** | +0.50 | 1 | 4 | +3 | — | 628 |
| `q_agg_03` | aggregation | 1.0000 | **1.0000** | +0.00 | 5 | 8 | +3 | — | 1140 |
| `q_agg_04` | aggregation | 0.5000 | **0.5000** | +0.00 | 1 | 4 | +3 | — | 737 |
| `q_agg_05` | aggregation | 1.0000 | **1.0000** | +0.00 | 1 | 3 | +2 | — | 595 |
| `q_agg_06` | aggregation | 0.5000 | **1.0000** | +0.50 | 2 | 2 | +0 | — | 404 |
| `q_agg_07` | aggregation | 1.0000 | **1.0000** | +0.00 | 5 | 8 | +3 | — | 1303 |
| `q_agg_08` | aggregation | 1.0000 | **1.0000** | +0.00 | 2 | 4 | +2 | — | 580 |
| `q_agg_09` | aggregation | 1.0000 | **0.5000** | -0.50 | 3 | 4 | +1 | — | 626 |
| `q_agg_10` | aggregation | 1.0000 | **0.5000** | -0.50 | 5 | 8 | +3 | — | 1104 |
| `q_oos_01` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 120 |
| `q_oos_02` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 120 |
| `q_oos_03` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 120 |
| `q_oos_04` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 120 |
| `q_oos_05` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 120 |
| `q_oos_06` | out-of-scope | — | **—** | — | 1 | 1 | +0 | — | 145 |
| `q_oos_07` | out-of-scope | — | **—** | — | 2 | 2 | +0 | — | 218 |
| `q_oos_08` | out-of-scope | — | **—** | — | 2 | 2 | +0 | — | 265 |
| `q_oos_09` | out-of-scope | — | **—** | — | 2 | 2 | +0 | — | 262 |
| `q_oos_10` | out-of-scope | — | **—** | — | 2 | 2 | +0 | — | 180 |
