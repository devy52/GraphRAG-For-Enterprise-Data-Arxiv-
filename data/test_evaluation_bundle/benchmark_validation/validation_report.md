# Benchmark Validation Report

_Generated 2026-10-03 14:40:05_

## 1. Deterministic recompute (stored vs independent implementation)

| run | n | max abs F1 diff | EM mismatches |
|---|---|---|---|
| baseline | 10 | 0.00e+00 | 0 |
| optimized | 10 | 0.00e+00 | 0 |

## 2. Paired comparison baseline -> optimized (bootstrap 95% CI)

Paired questions: 10. ADR-033-affected (vector/both route in optimized run): ['q_1hop_02', 'q_1hop_06', 'q_1hop_10']

| metric | subset | n | baseline | optimized | mean delta | 95% CI | significant |
|---|---|---|---|---|---|---|---|
| rag.faithfulness | all | 10 | 1.000 | 0.895 | -0.105 | [-0.305, +0.000] | False |
| rag.faithfulness | vector_routed | 3 | 1.000 | 0.983 | -0.017 | [-0.050, +0.000] | False |
| rag.hallucination_rate | all | 10 | 0.000 | 0.105 | +0.105 | [+0.000, +0.305] | False |
| rag.hallucination_rate | vector_routed | 3 | 0.000 | 0.017 | +0.017 | [+0.000, +0.050] | False |
| rag.context_precision | all | 10 | 0.300 | 0.405 | +0.105 | [-0.020, +0.260] | False |
| rag.context_precision | vector_routed | 3 | 0.200 | 0.500 | +0.300 | [-0.050, +0.650] | False |
| rag.answer_relevancy | all | 10 | 0.465 | 0.605 | +0.140 | [-0.130, +0.425] | False |
| rag.answer_relevancy | vector_routed | 3 | 0.683 | 0.983 | +0.300 | [+0.000, +0.900] | False |
| retrieval.chunk_utilization | all | 10 | 0.260 | 0.420 | +0.160 | [+0.000, +0.360] | False |
| retrieval.chunk_utilization | vector_routed | 3 | 0.133 | 0.333 | +0.200 | [+0.000, +0.300] | False |
| text_similarity.f1 | all | 10 | 0.189 | 0.236 | +0.047 | [+0.003, +0.113] | True |
| text_similarity.f1 | vector_routed | 3 | 0.193 | 0.297 | +0.104 | [+0.000, +0.311] | False |

Routes per question (baseline -> optimized):

- q_1hop_01: graph -> graph
- q_1hop_02: vector -> vector
- q_1hop_03: graph -> graph
- q_1hop_04: graph -> graph
- q_1hop_05: graph -> graph
- q_1hop_06: vector -> vector
- q_1hop_07: graph -> graph
- q_1hop_08: graph -> graph
- q_1hop_09: graph -> graph
- q_1hop_10: vector -> vector

## 3. Objective (judge-free) outcomes on fresh live capture

| id | route | outcome | kw_recall | answerable in text corpus | best chunk | chunk_util (recomputed) |
|---|---|---|---|---|---|---|
| q_1hop_01 | graph | keyword_correct | 1.00 | True (0.67) | chunk_arxiv_2005_11401_extra_0 | 1.00 |
| q_1hop_02 | vector | keyword_correct | 0.50 | True (1.00) | chunk_arxiv_2005_11401_000 | 0.50 |
| q_1hop_03 | graph | keyword_correct | 0.67 | True (0.67) | chunk_arxiv_2004_04906_000 | 0.20 |
| q_1hop_04 | graph | missed_answerable_abstained | 0.00 | True (1.00) | chunk_arxiv_2004_04906_000 | 0.00 |
| q_1hop_05 | graph | keyword_correct | 1.00 | True (1.00) | chunk_arxiv_2004_12832_000 | 1.00 |
| q_1hop_06 | vector | keyword_wrong | 0.33 | True (0.67) | chunk_arxiv_2004_04906_000 | 0.00 |
| q_1hop_07 | graph | missed_answerable_abstained | 0.00 | True (1.00) | chunk_arxiv_2004_04906_000 | 0.00 |
| q_1hop_08 | graph | missed_answerable_abstained | 0.00 | True (1.00) | chunk_arxiv_2005_11401_000 | 0.12 |
| q_1hop_09 | graph | keyword_wrong | 0.00 | True (1.00) | chunk_arxiv_2004_04906_000 | 1.00 |
| q_1hop_10 | vector | keyword_correct | 1.00 | True (1.00) | chunk_arxiv_2004_04906_000 | 0.00 |

Outcome counts: {'keyword_correct': 5, 'missed_answerable_abstained': 3, 'keyword_wrong': 2}

## 4a. Judge `nvidia/nemotron-3-super-120b-a12b` (primary)

- calls: 90, strict-parse failures: 90
- production-parser paths: {'api_error': 90}
- mean within-item std over 3 repeats (temp 0): {'faithfulness': nan, 'context_precision': nan, 'answer_relevancy': nan}

## 4b. Judge `openai/gpt-oss-20b` (alt)

- calls: 90, strict-parse failures: 0
- production-parser paths: {'json': 90}
- mean within-item std over 3 repeats (temp 0): {'faithfulness': 0.04714045207910317, 'context_precision': 0.03472377675605569, 'answer_relevancy': 0.009428090415820633}

## 5. Cross-judge agreement (primary vs alt, item-level means)

| metric | Spearman | mean |primary-alt| |
|---|---|---|
| faithfulness | n/a | nan |
| context_precision | n/a | nan |
| answer_relevancy | n/a | nan |

Per-question item means (primary / alt):

| id | faith P | faith A | prec P | prec A | rel P | rel A |
|---|---|---|---|---|---|---|
| q_1hop_01 | n/a | 1.00 | n/a | 1.00 | n/a | 0.95 |
| q_1hop_02 | n/a | 1.00 | n/a | 0.07 | n/a | 0.95 |
| q_1hop_03 | n/a | 0.33 | n/a | 0.10 | n/a | 1.00 |
| q_1hop_04 | n/a | 1.00 | n/a | 0.00 | n/a | 0.03 |
| q_1hop_05 | n/a | 1.00 | n/a | 0.97 | n/a | 0.95 |
| q_1hop_06 | n/a | 1.00 | n/a | 0.90 | n/a | 0.95 |
| q_1hop_07 | n/a | 1.00 | n/a | 0.07 | n/a | 0.00 |
| q_1hop_08 | n/a | 1.00 | n/a | 0.02 | n/a | 0.00 |
| q_1hop_09 | n/a | 0.50 | n/a | 0.13 | n/a | 0.03 |
| q_1hop_10 | n/a | 1.00 | n/a | 0.58 | n/a | 0.95 |
