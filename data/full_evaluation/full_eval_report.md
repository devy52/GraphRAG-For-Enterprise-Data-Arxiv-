# GraphRAG Full Evaluation Report

**Generated**: 2026-10-03 06:06 UTC
**Judge Mode**: `live` (scores are real LLM-judged)
**Total Examples**: 50

## Score Legitimacy Legend

| Tag | Meaning |
|---|---|
| ✅ `deterministic` | Algorithmically computed (token overlap, exact match). Always valid. |
| ✅ `legit (LLM-judged)` | Scored by a real LLM judge. Valid when `--mode live`. |
| ⚠️ `pseudo-random (dummy judge)` | Hash-derived fake score from DummyJudgeBackend. **NOT a real quality signal.** |

## Overall Scores (All 50 Questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.4120 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.1660 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 0.8110 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.1890 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.2009 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.1759 | ✅ deterministic |

## Per-Hop-Type Breakdown

### 1-hop (10 questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.7350 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.2450 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 0.5350 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.4650 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.5829 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.2217 | ✅ deterministic |

### 2-hop (10 questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.3850 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.2200 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 1.0000 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.0000 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.2000 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.0967 | ✅ deterministic |

### 3-hop (10 questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.3550 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.1950 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 0.9200 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.0800 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.0500 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.1180 | ✅ deterministic |

### aggregation (10 questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.5850 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.1700 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 0.6000 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.4000 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.0417 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.1183 | ✅ deterministic |

### out-of-scope (10 questions)

| Metric | Score | Legitimacy |
|---|---|---|
| `rag.answer_relevancy` | 0.0000 | ✅ legit (LLM-judged) |
| `rag.context_precision` | 0.0000 | ✅ legit (LLM-judged) |
| `rag.faithfulness` | 1.0000 | ✅ legit (LLM-judged) |
| `rag.hallucination_rate` | 0.0000 | ✅ legit (LLM-judged) |
| `retrieval.chunk_utilization` | 0.0000 | ✅ deterministic |
| `text_similarity.exact_match` | 0.0000 | ✅ deterministic |
| `text_similarity.f1` | 0.3250 | ✅ deterministic |

## Latency Summary

- **Mean**: 7631.9 ms
- **P50**: 5928.9 ms
- **P95**: 19815.3 ms

## How to Verify These Scores

### Deterministic metrics (always valid)
- `f1`, `exact_match`, `chunk_utilization`, `precision_at_k`, `recall_at_k`, `mrr`
- These are pure math — token overlap, set intersection, rank reciprocals.
- **Verification**: Pick any example, manually compute the token F1 between `adapter_output` and `reference`. It will match the reported score exactly.

### Judge-scored metrics (valid only with real LLM judge)
- `faithfulness`, `context_precision`, `answer_relevancy`, `hallucination_rate`
- With `--mode dummy`: scores are SHA-256 hash-derived pseudo-random numbers. **Ignore them.**
- With `--mode live`: an LLM reads the context+answer and scores 0.0–1.0.
- **Verification**: Run with `--mode live --judge-model gemini/gemini-2.0-flash` (or `gpt-4o-mini`), then compare against manual human judgment on 5–10 spot-check samples.
