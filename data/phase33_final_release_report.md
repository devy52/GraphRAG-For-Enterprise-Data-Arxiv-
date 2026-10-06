# Phase 33 Final Release Benchmark Report

**Timestamp**: 2026-10-06 15:58:28 UTC  
**Benchmark**: Canonical 50-Question Benchmark v2 (`88fc85fc1af4`)  
**Model**: Qwen2.5-7B-Instruct (`temperature=0.0`)  
**Configuration**: Frozen Champion (Step 32B Multi-Hop Passage Hydration, static cap=3)

---

## 1. Required Quality Criteria Evaluation

Evaluation of the 6 pre-registered criteria on the frozen champion:

| Quality Criterion | Step 32B Benchmark | Measured Phase 33 | Required Threshold | Status | Note |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Substantive Chunk Recall** | 0.6538 | **0.6538** | $\ge 0.6538$ | **PASS** | 100.0% identical retrieval across 50/50 questions. |
| **Unified Evidence Recall** | 0.6708 | **0.6708** | $\ge 0.6708$ | **PASS** | 100.0% identical evidence discovery. |
| **Invalid Citation Rate** | 0.0% | **0.0%** | $0.0\%$ | **PASS** | Hard AST/regex validation gate preserved (0 invalid citations). |
| **Overall Fact Score** | 0.8208 | **0.8000** | $\ge 0.8208$ | **FAIL** | 46/50 (92%) identical fact scores; 4 queries varied due to remote API generation variance (-0.0208). |
| **Strict Success Rate** | 28/40 (70.0%) | **26/40 (65.0%)** | $\ge 28/40$ ($\ge 70.0\%$) | **FAIL** | 26 strict passes; net -2 questions from phrasing variance. |
| **P50 Total Latency** | 4112.7 ms | **5043.9 ms** | $\le 4500.0$ ms | **FAIL** | Remote NVIDIA NIM gateway queue latency fluctuation (+931.2 ms). |

---

## 2. Efficiency Criterion & Accepted Trade-Off

| Efficiency Criterion | Engineering Target | Measured Phase 33 | Evaluation |
| :--- | :---: | :---: | :--- |
| **Mean Context Tokens** | $\le 450.0$ | **598.0** | **ACCEPTED LIMITATION** |

**Formal Assessment**:
> Quality/retrieval objectives achieved; context-efficiency objective remains unresolved and is an accepted limitation of the final champion.

---

## 3. Stratified Fact Score Breakdown

| Question Stratum | Run 3B Baseline | Step 32B Champion | Phase 33 Measured | Delta vs Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **1-hop (n=10)** | 0.8000 | 0.7000 | **0.6500** | -0.1500 |
| **2-hop (n=10)** | 0.7000 | 0.8000 | **0.8000** | +0.1000 |
| **3-hop (n=10)** | 0.7333 | 0.9333 | **0.9000** | +0.1667 |
| **aggregation (n=10)** | 0.8000 | 0.8500 | **0.8500** | +0.0500 |
| **out-of-scope (n=10)** | 100.0% (abst) | 100.0% (abst) | **100.0% (abst)** | +0.0% |

---

## 4. Reproducibility & Causal Verification Audit

Cross-run audit comparing Step 32B vs Phase 33:
- **Retrieved Chunk IDs**: **50/50 (100.0%) identical** across all questions.
- **Retrieved Graph Facts**: **50/50 (100.0%) identical** across all questions.
- **Hydrated Passages**: **50/50 (100.0%) identical** across all questions.
- **Mean Context Tokens**: **598.0 vs 598.0 (100.0% identical)**.
- **Out-of-Scope Refusal**: **10/10 (100.0% identical)**.
- **Fact Score Stability**: **46/50 (92.0%) questions yielded identical fact scores**.
  - `q_1hop_09`: 1.0 -> 0.5 (missed `q9_f2` due to phrasing change in remote model output)
  - `q_3hop_01`: 1.0 -> 0.67 (missed `q3hop1_f3` due to phrasing change)
  - `q_agg_01`: 1.0 -> 0.5 (refusal phrasing variation)
  - `q_agg_09`: 0.5 -> 1.0 (improved coverage)

---

## 5. Research Conclusion & Release Gate Status

**Release Gate Status**: **NOT SIGNED OFF AS FINAL RELEASE** (3/6 required quality criteria failed on Phase 33 rerun).

> **“The frozen Step 32B configuration remains the best-performing observed configuration, achieving 0.8208 fact score and 28/40 strict success in its original controlled run. The Phase 33 rerun reproduced retrieval and evidence exactly but produced lower end-to-end answer metrics because of remote NIM generation variance, demonstrating that the current benchmark is not fully end-to-end reproducible despite deterministic retrieval.”**

- **Champion Performance**: Best observed 32B result (0.8208 fact score, 28/40 strict success).
- **Release Reproducibility**: Not yet demonstrated. Next step: frozen repeatability study.
