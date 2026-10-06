# evalkit report

- **Generated:** 2026-10-05 16:04 UTC
- **Track:** `rag, retrieval, graph, text_similarity`
- **Dataset:** `data\temp_evalkit_dataset_5.jsonl` (5 examples)
- **Adapter:** `eval_adapter:GraphRAGAdapter`
- **Judge backend:** `litellm` (model: `fireworks_ai/accounts/fireworks/models/deepseek-v4p1-flash`)
- **Cache:** 0 hit(s), 25 miss(es)

## Summary

| Metric | Average |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 0.945 |
| graph.graph_utilization_rate | 0.000 |
| latency_ms | 3457.5ms |
| rag.answer_correctness | 0.200 |
| rag.answer_relevancy | 0.140 |
| rag.context_precision | 0.206 |
| rag.context_recall | 0.480 |
| rag.faithfulness | 0.800 |
| retrieval.chunk_utilization | 0.100 |
| retrieval.mrr | 0.300 |
| retrieval.ndcg_at_k | 0.314 |
| retrieval.precision_at_k | 0.226 |
| retrieval.recall_at_k | 0.500 |
| text_similarity.bleu | 0.065 |
| text_similarity.exact_match | 0.000 |
| text_similarity.f1 | 0.292 |
| text_similarity.rouge_l | 0.223 |

## Methodology

Track `rag, retrieval, graph, text_similarity`. Each metric is scored on a 0.0-1.0 scale (0.7 used as the pass/fail marker below), except raw measurements (cost, latency_ms), which show their actual unit and have no pass/fail marker here — gate those with an explicit `max` threshold instead.

- **cost**: Estimated monetary cost of the LLM generation and judge evaluation calls (USD).
- **graph.global_diversity**: Measures lexical non-repetition and thematic breadth (0.0 - 1.0) across distinct community themes for global/aggregation queries.
- **graph.graph_utilization_rate**: Fraction of retrieved graph facts/subgraph edges actually utilized or cited in the generated answer (0.0 - 1.0).
- **latency_ms**: Wall-clock time for the adapter call (time.monotonic() around adapter.run()), in milliseconds. Measures your system's response time, not judge/evaluator overhead.
- **rag.answer_correctness**: LLM judge scores 0.0-1.0: does the generated answer factually agree with the ground-truth reference answer?
- **rag.answer_relevancy**: LLM judge scores 0.0-1.0: does the answer address the question asked, independent of whether it's factually correct?
- **rag.context_precision**: LLM judge scores 0.0-1.0: how much of the retrieved context is actually relevant to answering the question (irrelevant passages lower it)?
- **rag.context_recall**: LLM judge scores 0.0-1.0: does the retrieved context contain the information necessary to support the reference answer?
- **rag.faithfulness**: LLM judge scores 0.0-1.0: does every claim in the answer trace back to the retrieved context, with no fabrication?
- **retrieval.chunk_utilization**: Heuristic: fraction of retrieved chunks with meaningful word-overlap with the output — an approximation of whether the generator used what was retrieved, not a precise measure. Needs no ground truth.
- **retrieval.mrr**: 1 / rank of the first relevant chunk in the retrieved list (0 if none found). Requires metadata.relevant_chunks in the dataset.
- **retrieval.ndcg_at_k**: Normalized Discounted Cumulative Gain at rank K. Computes position-discounted relevance gain normalized by ideal DCG. Supports binary or graded relevance.
- **retrieval.precision_at_k**: Fraction of retrieved chunks (top-K) that are in metadata.relevant_chunks (exact string match). Requires ground truth in the dataset.
- **retrieval.recall_at_k**: Fraction of all relevant chunks that were retrieved in top-K. Requires metadata.relevant_chunks in the dataset.
- **text_similarity.bleu**: Sentence-level BLEU score (sacrebleu), normalized to 0.0-1.0. N-gram precision against the reference.
- **text_similarity.exact_match**: 1.0 if output exactly matches reference (whitespace-trimmed), else 0.0.
- **text_similarity.f1**: SQuAD-style token-overlap F1 between output and reference. Deterministic, no LLM call.
- **text_similarity.rouge_l**: ROUGE-L F-measure (rouge-score), longest-common-subsequence overlap with the reference.

## Per-example results

### Example 1

**Input:**

```
Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning?
```

**Output:**

```
There is insufficient evidence in the provided context to determine the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning.
```

**Reference:**

```
The primary authors of GraphRAG-R1 are Chuanyue Yu, Kuo Zhao, Yuhan Li, and Heng Chang.
```

**Retrieved context:**

```
[graph] Entity 'Process-Constrained Reinforcement Learning' -[:USES_METHOD]- 'GraphRAG-R1' (Paper) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'Process-Constrained Reinforcement Learning' -[:USES_METHOD]- 'GraphRAG-R1' (Paper) [chunk: chunk_arxiv_2507_23581v2_000].
```

```
[graph] Entity 'GraphRAG-R1' -[:USES_DATASET]- 'out-of-domain datasets' (Dataset) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:USES_DATASET]- 'in-domain datasets' (Dataset) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:EXTENDS]- 'GraphRAG' (Method) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:PUBLISHED_IN]- 'arXiv' (Venue) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:HAS_TOPIC]- 'Graph Retrieval-Augmented Generation' (Topic) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:USES_METHOD]- 'Graph-textual retrieval' (Method) [chunk: chunk_arxiv_2507_23581v2_002].
```

**Scores:**

| Metric | Score |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 0.957 ✅ |
| graph.graph_utilization_rate | 0.000 ❌ |
| latency_ms | 4317.0ms |
| rag.answer_correctness | 0.000 ❌ |
| rag.answer_relevancy | 0.200 ❌ |
| rag.context_precision | 0.200 ❌ |
| rag.context_recall | 0.000 ❌ |
| rag.faithfulness | 1.000 ✅ |
| retrieval.chunk_utilization | 0.250 ❌ |
| retrieval.mrr | 0.500 ❌ |
| retrieval.ndcg_at_k | 0.631 ❌ |
| retrieval.precision_at_k | 0.500 ❌ |
| retrieval.recall_at_k | 1.000 ✅ |
| text_similarity.bleu | 0.073 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.308 ❌ |
| text_similarity.rouge_l | 0.308 ❌ |

### Example 2

**Input:**

```
Which reinforcement learning method does Chuanyue Yu and colleagues use to enhance reasoning in GraphRAG?
```

**Output:**

```
There is insufficient evidence in the provided context to determine which reinforcement learning method Chuanyue Yu and colleagues use to enhance reasoning in GraphRAG.
```

**Reference:**

```
Chuanyue Yu and colleagues propose GraphRAG-R1, which utilizes process-constrained reinforcement learning (RL) to guide graph traversal and reasoning.
```

**Retrieved context:**

```
[graph] Paper 'GraphRAG-Bench' uses method 'GraphRAG methods' [chunk: chunk_arxiv_2506_02404v3_002].
```

```
[graph] Paper 'GraphRAG-Bench' uses method 'GraphRAG' [chunk: chunk_arxiv_2506_02404v3_001].
```

```
[graph] Paper 'GraphRAG-Bench' uses method 'GraphRAG' [chunk: chunk_arxiv_2506_02404v3_000].
```

```
[graph] Paper 'GraphRAG-R1' uses method 'Graph-textual retrieval' [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Paper 'GraphRAG-R1' uses method 'Process-Constrained Reinforcement Learning' [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Paper 'GraphRAG-R1' uses method 'Process-Constrained Reinforcement Learning' [chunk: chunk_arxiv_2507_23581v2_000].
```

```
[graph] Paper 'GraphRAG-R1' uses method 'GraphRAG' [chunk: chunk_arxiv_2507_23581v2_000].
```

```
[graph] Paper 'HVM-GraphRAG' uses method 'Multimodal GraphRAG' [chunk: chunk_arxiv_2607_24861v1_000].
```

```
[graph] Paper 'HVM-GraphRAG' uses method 'GraphRAG' [chunk: chunk_arxiv_2607_24861v1_000].
```

```
[graph] Paper 'RAG vs. GraphRAG: A Systematic Evaluation and Key Insights' uses method 'GraphRAG' [chunk: chunk_arxiv_2502_11371v3_001].
```

```
[graph] Paper 'RAG vs. GraphRAG: A Systematic Evaluation and Key Insights' uses method 'RAG' [chunk: chunk_arxiv_2502_11371v3_001].
```

```
[graph] Paper 'ACE-GraphRAG' uses method 'RAG' [chunk: chunk_arxiv_2608_01269v2_001].
```

```
[graph] Paper 'ACE-GraphRAG' uses method 'GraphRAG' [chunk: chunk_arxiv_2608_01269v2_001].
```

```
[graph] Paper 'ACE-GraphRAG' uses method 'Parallel Differential Retrieval' [chunk: chunk_arxiv_2608_01269v2_000].
```

```
[graph] Paper 'ACE-GraphRAG' uses method 'GraphRAG' [chunk: chunk_arxiv_2608_01269v2_000].
```

```
[graph] Paper 'Plasma GraphRAG' uses method 'vanilla RAG' [chunk: chunk_arxiv_2604_06279v1_001].
```

```
[graph] Paper 'Plasma GraphRAG' uses method 'Large Language Models (LLMs)' [chunk: chunk_arxiv_2604_06279v1_000].
```

```
[graph] Paper 'Plasma GraphRAG' uses method 'GraphRAG' [chunk: chunk_arxiv_2604_06279v1_000].
```

```
[graph] Paper 'Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems' uses method 'GraphRAG' [chunk: chunk_arxiv_2604_09666v1_001].
```

```
[graph] Paper 'Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems' uses method 'RAG' [chunk: chunk_arxiv_2604_09666v1_001].
```

```
[graph] Paper 'Toward Robust GraphRAG: Mitigating Retrieval Drift and Hallucination from Imperfect Knowledge Graphs' uses method 'CS-RAG' [chunk: chunk_arxiv_2603_14828v2_001].
```

```
[graph] Paper 'Toward Robust GraphRAG: Mitigating Retrieval Drift and Hallucination from Imperfect Knowledge Graphs' uses method 'GraphRAG' [chunk: chunk_arxiv_2603_14828v2_001].
```

```
[graph] Paper 'GraphRAG' uses method 'RAG' [chunk: chunk_arxiv_2501_14050v4_000].
```

**Scores:**

| Metric | Score |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 0.958 ✅ |
| graph.graph_utilization_rate | 0.000 ❌ |
| latency_ms | 2331.4ms |
| rag.answer_correctness | 0.000 ❌ |
| rag.answer_relevancy | 0.300 ❌ |
| rag.context_precision | 0.130 ❌ |
| rag.context_recall | 0.700 ✅ |
| rag.faithfulness | 1.000 ✅ |
| retrieval.chunk_utilization | 0.000 ❌ |
| retrieval.mrr | 0.200 ❌ |
| retrieval.ndcg_at_k | 0.237 ❌ |
| retrieval.precision_at_k | 0.071 ❌ |
| retrieval.recall_at_k | 0.500 ❌ |
| text_similarity.bleu | 0.127 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.455 ❌ |
| text_similarity.rouge_l | 0.273 ❌ |

### Example 3

**Input:**

```
How does GraphRAG-R1's reinforcement learning framework enforce constraints on graph traversal during generation?
```

**Output:**

```
There is insufficient evidence in the provided context to answer how GraphRAG-R1's reinforcement learning framework enforces constraints on graph traversal during generation.
```

**Reference:**

```
GraphRAG-R1 integrates process-constrained reinforcement learning that constrains the reasoning process along valid graph structures, preventing hallucinated paths and improving factual consistency.
```

**Retrieved context:**

```
[graph] Entity 'Process-Constrained Reinforcement Learning' -[:USES_METHOD]- 'GraphRAG-R1' (Paper) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'Process-Constrained Reinforcement Learning' -[:USES_METHOD]- 'GraphRAG-R1' (Paper) [chunk: chunk_arxiv_2507_23581v2_000].
```

```
[graph] Entity 'Reinforcement Learning' -[:EXTENDS]- 'Distillation-Guided Policy Optimization' (Method) [chunk: chunk_arxiv_2508_20324v4_000].
```

```
[graph] Entity 'GraphRAG-R1' -[:USES_DATASET]- 'out-of-domain datasets' (Dataset) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:USES_DATASET]- 'in-domain datasets' (Dataset) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:EXTENDS]- 'GraphRAG' (Method) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:PUBLISHED_IN]- 'arXiv' (Venue) [chunk: chunk_arxiv_2507_23581v2_002].
```

```
[graph] Entity 'GraphRAG-R1' -[:HAS_TOPIC]- 'Graph Retrieval-Augmented Generation' (Topic) [chunk: chunk_arxiv_2507_23581v2_002].
```

**Scores:**

| Metric | Score |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 1.000 ✅ |
| graph.graph_utilization_rate | 0.000 ❌ |
| latency_ms | 3915.4ms |
| rag.answer_correctness | 0.000 ❌ |
| rag.answer_relevancy | 0.000 ❌ |
| rag.context_precision | 0.300 ❌ |
| rag.context_recall | 0.200 ❌ |
| rag.faithfulness | 1.000 ✅ |
| retrieval.chunk_utilization | 0.250 ❌ |
| retrieval.mrr | 0.500 ❌ |
| retrieval.ndcg_at_k | 0.387 ❌ |
| retrieval.precision_at_k | 0.333 ❌ |
| retrieval.recall_at_k | 0.500 ❌ |
| text_similarity.bleu | 0.041 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.255 ❌ |
| text_similarity.rouge_l | 0.213 ❌ |

### Example 4

**Input:**

```
Compare the primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA.
```

**Output:**

```
There is insufficient evidence to compare the primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA, as neither of these benchmarks is mentioned in the provided context.
```

**Reference:**

```
GraphRAG-Bench focuses on evaluating hierarchical knowledge retrieval and complex reasoning across four task difficulties, while IslamicFaithQA specifically evaluates hallucination, evidence grounding, and justified abstention on atomic single-gold questions.
```

**Retrieved context:**

```
[retrieved] estion design. Featuring college-level, domain-specific questions that demand multi-hop reasoning, the benchmark ensures that simple content retrieval is insufficient for problem-solving. For example, some questions require mathematical reasoning or programming. \((ii)\) Diverse task coverage. The dataset includes a broad spectrum of reasoning tasks, multiple-choice, true/false, multi-select, open-ended, and fill-in-the-blank. It spans 16 disciplines in twenty core textbooks. \((iii)\) Holistic evaluation framework. GraphRAG-Bench provides comprehensive assessment across the entire GraphRAG pipeline, including graph construction, knowledge retrieval, and answer generation. Beyond final-answer correctness, it evaluates the logical coherence of the reasoning process.
```

```
[retrieved] ls onboth hierarchical knowledge retrieval and deep contextual reasoning. GraphRAG-Bench features a comprehensive dataset with tasks of increasing difficulty, coveringfact retrieval, complex reasoning, contextual summarization, and creative generation, and a systematic evaluation across the entire pipeline, from graph constructionand knowledge retrieval to final generation. Leveraging this novel benchmark, we systematically investigate the conditions when GraphRAG surpasses traditional RAG and the underlying reasons for its success, offering guidelines for its practical application. All related resources and analyses are collected for the community at https://github.com/GraphRAG-Bench/GraphRAG-Benchmark.
```

```
[retrieved] nd agent-graph integration. Besides, we present a novel context engineering method for GraphRAG and Agentic RAG, addressing the context/memory overflow issues, efficiently managing text and graph retrievals with new representations and agentic loop design, leading to 19%-53% reduction on token usage. Moreover, further analysis identifies a retrieval-generation gap where expanded retrieval does not proportionally improve generation quality, suggesting retrieval-oriented metrics overstate advanced retrieval benefits. This work provides data-driven insights on when and how to use them for building production-ready intelligent RAG systems.
```

**Scores:**

| Metric | Score |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 0.942 ✅ |
| graph.graph_utilization_rate | — |
| latency_ms | 3218.9ms |
| rag.answer_correctness | 0.000 ❌ |
| rag.answer_relevancy | 0.200 ❌ |
| rag.context_precision | 0.400 ❌ |
| rag.context_recall | 0.500 ❌ |
| rag.faithfulness | 0.000 ❌ |
| retrieval.chunk_utilization | 0.000 ❌ |
| retrieval.mrr | 0.000 ❌ |
| retrieval.ndcg_at_k | 0.000 ❌ |
| retrieval.precision_at_k | 0.000 ❌ |
| retrieval.recall_at_k | 0.000 ❌ |
| text_similarity.bleu | 0.018 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.179 ❌ |
| text_similarity.rouge_l | 0.143 ❌ |

### Example 5

**Input:**

```
What is the biochemical mechanism of light-independent reactions in C4 carbon fixation?
```

**Output:**

```
There is insufficient evidence in the provided context to answer the question about the biochemical mechanism of light-independent reactions in C4 carbon fixation. The context only discusses Agentic Retrieval-Augmented Generation (RAG) and its applications, and does not mention C4 carbon fixation or biochemical mechanisms.
```

**Reference:**

```
I cannot answer this question because the provided enterprise research corpus contains no evidence on plant biology, photosynthesis, or C4 carbon fixation.
```

**Retrieved context:**

```
[retrieved] ranscends these limitations by embedding autonomous AI agents into the RAG pipeline. These agents leverage agentic design patterns reflection, planning, tool use, and multi-agent collaboration to dynamically manage retrieval strategies, iteratively refine contextual understanding, and adapt workflows through operational structures ranging from sequential steps to adaptive collaboration. This integration enables Agentic RAG systems to deliver flexibility, scalability, and context-awareness across diverse applications. This paper presents an analytical survey of Agentic RAG systems.
```

**Scores:**

| Metric | Score |
|---|---|
| cost | $0.000000 |
| graph.global_diversity | 0.869 ✅ |
| graph.graph_utilization_rate | — |
| latency_ms | 3504.8ms |
| rag.answer_correctness | 1.000 ✅ |
| rag.answer_relevancy | 0.000 ❌ |
| rag.context_precision | 0.000 ❌ |
| rag.context_recall | 1.000 ✅ |
| rag.faithfulness | 1.000 ✅ |
| retrieval.chunk_utilization | 0.000 ❌ |
| retrieval.mrr | — |
| retrieval.ndcg_at_k | — |
| retrieval.precision_at_k | — |
| retrieval.recall_at_k | — |
| text_similarity.bleu | 0.064 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.265 ❌ |
| text_similarity.rouge_l | 0.176 ❌ |
