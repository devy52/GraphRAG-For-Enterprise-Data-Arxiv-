# A/B/C/D Ablation Benchmark Report: Isolating Retrieval vs. Generation

Generated: `2026-10-06T07:00:15.526101+00:00`  
Dataset SHA-256: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  
Total Questions Evaluated: **50**  

## 1. High-Level Performance Comparison

| Metric | Vector | Graph | Hybrid | Oracle |
|---|:---:|:---:|:---:|:---:|
| **Fact Score** | 0.6292 | 0.4625 | 0.6750 | 0.9458 |
| **Strict Success** | 42.5% | 20.0% | 42.5% | 90.0% |
| **Chunk Recall** | 0.2692 | — | 0.2821 | — |
| **Graph Recall** | — | 0.5000 | 0.5000 | — |
| **Metadata Recall** | 0.0000 | 0.0000 | 0.0000 | — |
| **Unified Recall** | 0.2625 | 0.4750 | 0.5500 | 1.0000 |
| **Context Tokens (Est)** | 247 | 205.06 | 448.58 | 180.14 |
| **Latency p50 (ms)** | 3594.3 ms | 3733.3 ms | 4187.99 ms | 1922.91 ms |
| **Latency p95 (ms)** | 28875.06 ms | 34029.12 ms | 15396.46 ms | 19655.04 ms |
| **Abstention Accuracy** | 100.0% | 100.0% | 100.0% | 100.0% |

## 1.1 Causal Attribution Analysis

- **Retrieval-Caused Failures**: Gaps where required chunks, entities, or metadata were missing from the retrieval candidate pool.
- **Evidence Assembly-Caused Failures**: Cases where evidence was retrieved, but context formatting or token drowning degraded generator synthesis.
- **Ceiling (Oracle)**: Performance achieved when 100% authoritative gold evidence is provided directly to the generator.

## 2. Per-Tier Fact Score Breakdown

| Tier | Mode A (Vector) | Mode B (Graph) | Mode C (Hybrid) | Mode D (Oracle) |
|---|---:|---:|---:|---:|
| `1-hop` | 0.4000 | 0.3000 | 0.5500 | 1.0000 |
| `2-hop` | 0.7000 | 0.2500 | 0.7000 | 0.8500 |
| `3-hop` | 0.6667 | 0.6000 | 0.7000 | 0.9333 |
| `aggregation` | 0.7500 | 0.7000 | 0.7500 | 1.0000 |
| `out-of-scope` (Abstention) | 100.0% | 100.0% | 100.0% | 100.0% |

## 3. Worst 10 Hybrid Cases Diagnostic Triage

Taxonomy:
- **Type A**: Correct evidence not retrieved
- **Type B**: Graph traversal found wrong or incomplete evidence
- **Type C**: Evidence retrieved but assembled in confusing order
- **Type D**: Context polluted / drowned by irrelevant evidence
- **Type E**: Sufficient context present, but LLM failed to synthesize
- **Type F**: Citation/provenance failure

| ID | Tier | Retrieval | Evidence | Context | Generation | Failure | Hybrid Fact | Oracle Fact | Reasoning |
|---|---|:---:|:---:|:---:|:---:|:---:|---:|---:|---|
| `q_1hop_01` | EvalHopTypeV2.ONE_HOP | ✅ | ❌ | ✅ | ❌ | **B** | 0.0000 | 1.0000 | Graph traversal found relationships, but missed target gold chunks |
| `q_1hop_02` | EvalHopTypeV2.ONE_HOP | ✅ | ❌ | ✅ | ❌ | **B** | 0.0000 | 1.0000 | Graph traversal found relationships, but missed target gold chunks |
| `q_1hop_03` | EvalHopTypeV2.ONE_HOP | ✅ | ❌ | ✅ | ❌ | **B** | 0.0000 | 1.0000 | Graph traversal found relationships, but missed target gold chunks |
| `q_2hop_06` | EvalHopTypeV2.TWO_HOP | ✅ | ✅ | ✅ | ❌ | **E** | 0.0000 | 1.0000 | Gold chunk retrieved (recall 1.00), Oracle got 1.00, but Hybrid LLM answer failed fact coverage (0.00) |
| `q_3hop_03` | EvalHopTypeV2.THREE_HOP | ✅ | ❌ | ✅ | ❌ | **E** | 0.3333 | 1.0000 | Gold chunk retrieved (recall 0.50), Oracle got 1.00, but Hybrid LLM answer failed fact coverage (0.33) |
| `q_3hop_09` | EvalHopTypeV2.THREE_HOP | ✅ | ✅ | ✅ | ❌ | **E** | 0.3333 | 1.0000 | Gold chunk retrieved (recall 1.00), Oracle got 1.00, but Hybrid LLM answer failed fact coverage (0.33) |
| `q_1hop_04` | EvalHopTypeV2.ONE_HOP | ✅ | ❌ | ✅ | ❌ | **E** | 0.5000 | 1.0000 | Gold chunk retrieved (recall 0.50), Oracle got 1.00, but Hybrid LLM answer failed fact coverage (0.50) |
| `q_1hop_06` | EvalHopTypeV2.ONE_HOP | ✅ | ❌ | ✅ | ❌ | **B** | 0.5000 | 1.0000 | Graph traversal found relationships, but missed target gold chunks |
| `q_1hop_09` | EvalHopTypeV2.ONE_HOP | ✅ | ✅ | ✅ | ❌ | **E** | 0.5000 | 1.0000 | Gold chunk retrieved (recall 1.00), Oracle got 1.00, but Hybrid LLM answer failed fact coverage (0.50) |
| `q_2hop_03` | EvalHopTypeV2.TWO_HOP | ✅ | ✅ | ❌ | ❌ | **C** | 0.5000 | 0.0000 | Partial evidence retrieved but relational continuity broken across context blocks |
