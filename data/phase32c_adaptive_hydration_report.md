# Phase 32C Benchmark Report: Evidence-Gap Adaptive Passage Hydration

**Timestamp**: 2026-10-06 15:35:23 UTC  
**Benchmark**: Canonical 50-Question Benchmark v2 (`88fc85fc1af4`)  
**Model**: Qwen2.5-7B-Instruct (`temperature=0.0`)  
**Architecture Policy**: Evidence-Gap Adaptive Hydration (ADR 062 / Step 32C)

---

## 1. Executive Summary & Gate Evaluation

Step 32C implements runtime evidence-gap budgeting (0, 1, or min(|U|, 3)) using strictly retrieval-time signals (vector score profile, paper coverage, and graph structural traversal characteristics). It eliminates spurious 1-hop cross-paper hydration while preserving 100% of multi-hop bridging hydration.

| Acceptance Gate | Run 3B Baseline | Step 32B Control | Step 32C Measured | Target Condition | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Mean Context Tokens** | 392.2 | 598.0 | **541.7** | $\le 450.0$ | **FAIL** |
| **Overall Fact Score** | 0.7583 | 0.8208 | **0.7958** | $\ge 0.8208$ | **FAIL** |
| **Strict Success Rate** | 24/40 (60.0%) | 28/40 (70.0%) | **27/40 (67.5%)** | $\ge 28/40$ | **FAIL** |
| **Substantive Chunk Recall** | 0.2821 | 0.6538 | **0.5513** | $\ge 0.6538$ | **FAIL** |
| **Unified Evidence Recall** | 0.3083 | 0.6708 | **0.5708** | $\ge 0.6708$ | **FAIL** |
| **P50 Total Latency** | 4115.6 ms | 4112.7 ms | **4660.2 ms** | $\le 4500.0$ ms | **FAIL** |
| **Invalid Citation Rate** | 0.0% | 0.0% | **0.0%** | $0.0\%$ | **PASS** |
| **1-Hop Fact Score Recovery** | 0.8000 | 0.7000 | **0.7000** | $\ge 0.8000$ | **FAIL** |

---

## 2. Hop-by-Hop Fact Score Stratification

| Question Class | Run 3B Baseline | Step 32B Control | Step 32C Measured | 32C vs 32B Delta |
| :--- | :---: | :---: | :---: | :---: |
| **1-hop (n=10)** | 0.8000 | 0.7000 | **0.7000** | +0.0000 |
| **2-hop (n=10)** | 0.7000 | 0.8000 | **0.7000** | -0.1000 |
| **3-hop (n=10)** | 0.7333 | 0.9333 | **0.9333** | +0.0000 |
| **aggregation (n=10)** | 0.8000 | 0.8500 | **0.8500** | +0.0000 |
| **out-of-scope (n=10)** | — (abst) | 1.0000 (abst) | **1.0000 (abst)** | +0.0000 |

---

## 3. Adaptive Hydration Telemetry & Decision Breakdown

* **Total Candidates Discovered**: 177
* **Total Chunks Selected for Hydration**: 55
* **Total Chunks Hydrated via PostgreSQL**: 55
* **Total Candidates Dropped due to Budget**: 84
* **Hydration Batch Lookup Latency**: p50 = 5.92 ms, p95 = 7.03 ms

### Decision Reasons Distribution
- `direct_vector_sufficient`: 3 queries
- `minor_gap`: 14 queries
- `multi_hop_gap`: 17 queries
- `no_graph_candidates`: 10 queries
- `no_unseen_graph_chunks`: 6 queries

---

## 4. Causal Verification & Research Conclusion

### Causal Isolation Verification
- **Candidate Chunk IDs Identical**: 50/50 queries (100.0%)
- **Graph Facts Identical**: 50/50 queries (100.0%)
- **Result**: Within the controlled 32B vs 32C experiment, upstream evidence discovery was identical; therefore the measured performance differences are attributable to adaptive hydration budget slicing.

### Research Conclusion
Static graph-guided hydration is highly effective at recovering missing evidence, but unconditional hydration increases context substantially. The tested runtime evidence-gap heuristic failed to preserve those gains and introduced additional regressions. Therefore, the static 3-passage hydration configuration remains the best observed system configuration, while adaptive budgeting remains an unresolved research problem.

**Verdict**: Step 32C ❌ rejected. Step 32B ✅ frozen as current performance control/champion for Phase 33 (not yet designated production-ready pending explicit resolution or acceptance of the 598-token context trade-off).
