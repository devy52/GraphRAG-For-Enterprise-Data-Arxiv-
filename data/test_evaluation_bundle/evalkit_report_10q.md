# evalkit report

- **Generated:** 2026-10-03 04:30 UTC
- **Track:** `rag, text_similarity`
- **Dataset:** `data\temp_evalkit_dataset_10.jsonl` (10 examples)
- **Adapter:** `eval_adapter:GraphRAGAdapter`
- **Judge backend:** `dummy` (model: `dummy`)

> ⚠️ **Scores below are not meaningful.** The `dummy` judge backend produces a deterministic pseudo-score for exercising the pipeline offline — it does not evaluate quality. Switch to `judge_backend: litellm` (or another real backend) for actual scores.

## Summary

| Metric | Average |
|---|---|
| latency_ms | 7807.5ms |
| rag.answer_relevancy | 0.525 |
| rag.context_precision | 0.655 |
| rag.faithfulness | 0.594 |
| text_similarity.exact_match | 0.000 |
| text_similarity.f1 | 0.211 |

## Methodology

Track `rag, text_similarity`. Each metric is scored on a 0.0-1.0 scale (0.7 used as the pass/fail marker below), except raw measurements (latency_ms), which show their actual unit and have no pass/fail marker here — gate those with an explicit `max` threshold instead.

- **latency_ms**: No description provided by this evaluator.
- **rag.answer_relevancy**: No description provided by this evaluator.
- **rag.context_precision**: No description provided by this evaluator.
- **rag.faithfulness**: No description provided by this evaluator.
- **text_similarity.exact_match**: No description provided by this evaluator.
- **text_similarity.f1**: No description provided by this evaluator.

## Per-example results

### Example 1

**Input:**

```
Who are the primary authors of the Dense Passage Retrieval paper?
```

**Output:**

```
The primary authors of the Dense Passage Retrieval paper are Vladimir Karpukhin [chunk_arxiv_2004_04906_000], Barlas Oguz [chunk_arxiv_2004_04906_000], and Patrick Lewis [chunk_arxiv_2004_04906_000].
```

**Reference:**

```
Key entities: Dense Passage Retrieval, Patrick Lewis. Expected facts: Vladimir Karpukhin, Barlas Oguz, Patrick Lewis.
```

**Retrieved context:**

```
[graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Vladimir Karpukhin [chunk: chunk_arxiv_2004_04906_000].
```

```
[graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Barlas Oguz [chunk: chunk_arxiv_2004_04906_000].
```

```
[graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Patrick Lewis [chunk: chunk_arxiv_2004_04906_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 10344.7ms |
| rag.answer_relevancy | 0.500 ❌ |
| rag.context_precision | 0.771 ✅ |
| rag.faithfulness | 0.716 ✅ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.514 ❌ |

### Example 2

**Input:**

```
What primary model architecture is proposed in the RAG paper?
```

**Output:**

```
The primary model architecture proposed is a hierarchical heterogeneous hypergraph that aligns multi‑granular knowledge and incorporates deductive pathways to simulate realistic memory structures, as introduced in the IGMiRAG framework [chunk_arxiv_2602_07525v1_000].
```

**Reference:**

```
Key entities: Retrieval-Augmented Generation. Expected facts: RAG-Sequence, RAG-Token, generator, retriever.
```

**Retrieved context:**

```
[retrieved] Large language models (LLMs) are very costly and inefficient to update with new information. To address this limitation, retrieval-augmented generation (RAG) has been proposed as a solution that dynamically incorporates external knowledge during inference, improving factual consistency and reducing hallucinations. Despite its promise, RAG systems face practical challenges-most notably, a strong dependence on the quality of the input query for accurate retrieval. In this paper, we investigate the sensitivity of different components in the RAG pipeline to various types of query perturbations. Our analysis reveals that the performance of commonly used retrievers can degrade significantly even under minor query variations.
```

```
[retrieved] s efficient optimization through problem decomposition. Experimental results show that our method effectively mitigates generation bias while preserving relevance. This work provides a principled approach for fairness-aware retrieval in RAG systems.
```

```
[retrieved] ral Questions (NQ) dataset show that combining predictors from multiple feature categories yields the most accurate estimates of RAG performance.
```

```
[retrieved] Retrieval-augmented generation (RAG) equips large language models (LLMs) with reliable knowledge memory. To strengthen cross-text associations, recent research integrates graphs and hypergraphs into RAG to capture pairwise and multi-entity relations as structured links. However, their misaligned memory organization necessitates costly, disjointed retrieval. To address these limitations, we propose IGMiRAG, a framework inspired by human intuition-guided reasoning. It constructs a hierarchical heterogeneous hypergraph to align multi-granular knowledge, incorporating deductive pathways to simulate realistic memory structures.
```

```
[retrieved] Large Language Models (LLMs) have demonstrated impressive ability in generation and reasoning tasks but struggle with handling up-to-date knowledge, leading to inaccuracies or hallucinations. Retrieval-Augmented Generation (RAG) mitigates this by retrieving and incorporating external knowledge into input prompts. In particular, due to LLMs' context window limitations and long-context hallucinations, only the most relevant "chunks" are retrieved.
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 13086.6ms |
| rag.answer_relevancy | 0.768 ✅ |
| rag.context_precision | 0.788 ✅ |
| rag.faithfulness | 0.673 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.000 ❌ |

### Example 3

**Input:**

```
What dataset was used to evaluate Natural Questions in DPR?
```

**Output:**

```
The dataset used to evaluate Natural Questions in DPR is the Dense Passage Retrieval for Open-Domain Question Answering paper. [chunk_arxiv_2004_04906_000]
```

**Reference:**

```
Key entities: Natural Questions, Dense Passage Retrieval. Expected facts: Natural Questions, NQ, Wikipedia.
```

**Retrieved context:**

```
[graph] Entity 'Natural Questions (NQ)' -[:USES_DATASET]- 'Dense Passage Retrieval for Open-Domain Question Answering' (Paper) [chunk: chunk_arxiv_2004_04906_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 14480.0ms |
| rag.answer_relevancy | 0.735 ✅ |
| rag.context_precision | 0.466 ❌ |
| rag.faithfulness | 0.807 ✅ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.294 ❌ |

### Example 4

**Input:**

```
Which sparse retrieval baseline did DPR compare against?
```

**Output:**

```
The provided context does not contain any information about which sparse retrieval baseline DPR compared against, so there is insufficient evidence to answer the question.
```

**Reference:**

```
Key entities: Dense Passage Retrieval, BM25. Expected facts: BM25, Lucene.
```

**Retrieved context:**

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'TriviaQA' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2007_01282_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'TriviaQA' [chunks: chunk_arxiv_2004_04906_000, chunk_arxiv_2007_01282_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'TriviaQA' [chunks: chunk_arxiv_2004_04906_000, chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'TriviaQA' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2004_04906_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2007_01282_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_000, chunk_arxiv_2007_01282_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2004_12832_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_000, chunk_arxiv_2004_12832_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_000, chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'WebQuestions' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2004_04906_000].
```

```
[graph] Methods 'Dense Passage Retrieval (DPR)' and 'BART' are both evaluated on dataset 'MS MARCO' [chunks: chunk_arxiv_2004_04906_extra_0, chunk_arxiv_2004_12832_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 3865.5ms |
| rag.answer_relevancy | 0.286 ❌ |
| rag.context_precision | 0.932 ✅ |
| rag.faithfulness | 0.148 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.057 ❌ |

### Example 5

**Input:**

```
Who authored the ColBERT late-interaction retrieval paper?
```

**Output:**

```
The ColBERT late‑interaction retrieval paper was authored by Omar Khattab and Matei Zaharia [chunk_arxiv_2004_12832_000].
```

**Reference:**

```
Key entities: ColBERT. Expected facts: Omar Khattab, Matei Zaharia.
```

**Retrieved context:**

```
[graph] Paper 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT' was authored by Omar Khattab [chunk: chunk_arxiv_2004_12832_000].
```

```
[graph] Paper 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT' was authored by Matei Zaharia [chunk: chunk_arxiv_2004_12832_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 6801.7ms |
| rag.answer_relevancy | 0.523 ❌ |
| rag.context_precision | 0.859 ✅ |
| rag.faithfulness | 0.694 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.417 ❌ |

### Example 6

**Input:**

```
What loss function does DPR use for training its dual encoders?
```

**Output:**

```
DPR uses a negative log‑likelihood contrastive loss with in‑batch and BM25 hard negatives for training its dual encoders [chunk_arxiv_2004_04906_000].
```

**Reference:**

```
Key entities: Dense Passage Retrieval. Expected facts: negative log-likelihood, contrastive, in-batch negatives.
```

**Retrieved context:**

```
[retrieved] Open-domain question answering relies on efficient passage retrieval to select candidate contexts. We show that retrieval can be practically implemented using dense representations, where embeddings are learned from a small number of questions and passages by a simple dual-encoder framework. When evaluated on a wide range of open-domain QA datasets including Natural Questions (NQ), TriviaQA, and WebQuestions, our Dense Passage Retrieval (DPR) system outperforms strong Lucene BM25 sparse retrieval baselines by a wide margin. DPR uses a BERT-base encoder backbone with 768 embedding dimension and negative log-likelihood contrastive loss with in-batch and BM25 hard negatives. Fast MIPS passage search is executed using FAISS Flat and HNSW index types.
```

```
[retrieved] Dense Passage Retrieval (DPR) pairs with generator models such as BART and T5 for open-domain question answering. Methods extending DPR's dual-encoder architecture and hard negative mining include ANCE, RocketQA, and ColBERT. Both DPR and ColBERT evaluate on shared benchmark datasets including MS MARCO, Natural Questions, and TriviaQA. HotpotQA evaluates multi-hop reasoning over documents retrieved by DPR and dense retrievers.
```

```
[retrieved] RAG datastore. By crafting natural-text queries that are answerable only with the target document's presence, our approach demonstrates successful inference with just 30 queries while remaining stealthy; straightforward detectors identify adversarial prompts from existing methods up to ~76x more frequently than those generated by our attack. We observe a 2x improvement in TPR@1%FPR over prior inference attacks across diverse RAG configurations, all while costing less than $0.02 per document inference.
```

```
[retrieved] , ToR achieves state-of-the-art performance in both retrieval and response generation. In addition, we propose two tree-based search optimization strategies, pruning and effective expansion, to reduce time overhead and increase the diversity of path extension. We will release our code.
```

```
[retrieved] r improvements or no significant regression on the remaining tasks. Furthermore, we demonstrate our multi-task training with relevance label sampling scales well with increased model capacity and achieves state-of-the-art results in five out of seven KILT tasks.
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 3487.8ms |
| rag.answer_relevancy | 0.715 ✅ |
| rag.context_precision | 0.187 ❌ |
| rag.faithfulness | 0.892 ✅ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.400 ❌ |

### Example 7

**Input:**

```
What encoder backbone was used in the original DPR experiments?
```

**Output:**

```
The provided context does not contain information about the encoder backbone used in the original DPR experiments, so there is insufficient evidence to answer the question.
```

**Reference:**

```
Key entities: Dense Passage Retrieval, BERT. Expected facts: BERT, BERT-base.
```

**Retrieved context:**

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'ColBERT' (Method) [chunk: chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'RocketQA' (Method) [chunk: chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'BART' (Method) [chunk: chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:USES_METHOD]- 'Dense Passage Retrieval for Open-Domain Question Answering' (Paper) [chunk: chunk_arxiv_2004_04906_extra_0].
```

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:COMPARED_WITH]- 'Lucene BM25' (Method) [chunk: chunk_arxiv_2004_04906_000].
```

```
[graph] Entity 'Dense Passage Retrieval (DPR)' -[:USES_METHOD]- 'Dense Passage Retrieval for Open-Domain Question Answering' (Paper) [chunk: chunk_arxiv_2004_04906_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 3901.0ms |
| rag.answer_relevancy | 0.394 ❌ |
| rag.context_precision | 0.780 ✅ |
| rag.faithfulness | 0.713 ✅ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.000 ❌ |

### Example 8

**Input:**

```
What generator model is paired with the DPR retriever in the RAG paper?
```

**Output:**

```
The provided context does not contain the specific details about which generator model is paired with the DPR retriever in the Retrieval‑Augmented Generation paper, so there is insufficient evidence to answer the question.
```

**Reference:**

```
Key entities: Retrieval-Augmented Generation, BART. Expected facts: BART, BART-large.
```

**Retrieved context:**

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks' (Paper) [chunk: chunk_arxiv_2005_11401_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Fairness-Aware Retrieval Optimization for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2605_15790v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Predicting Retrieval Utility and Answer Quality in Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2601_14546v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'R^3AG: Retriever Routing for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2604_22849v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'VISA: Retrieval Augmented Generation with Visual Source Attribution' (Paper) [chunk: chunk_arxiv_2412_14457v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Accelerating Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2412_15246v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Towards Mixed-Modal Retrieval for Universal Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2510_17354v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'VeriCite: Towards Reliable Citations in Retrieval-Augmented Generation via Rigorous Verification' (Paper) [chunk: chunk_arxiv_2510_11394v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Video Enriched Retrieval Augmented Generation Using Aligned Video Captions' (Paper) [chunk: chunk_arxiv_2405_17706v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'A Retrieval-Augmented Generation Framework for Academic Literature Navigation in Data Science' (Paper) [chunk: chunk_arxiv_2412_15404v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'mKG-RAG: Leveraging Multimodal Knowledge Graphs in Retrieval-Augmented Generation for Knowledge-intensive VQA' (Paper) [chunk: chunk_arxiv_2508_05318v2_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Investigating the Robustness of Retrieval-Augmented Generation at the Query Level' (Paper) [chunk: chunk_arxiv_2507_06956v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Parser, Chunking, and Embedding Interactions in Retrieval-Augmented Generation over Indian Government Regulatory Documents' (Paper) [chunk: chunk_arxiv_2609_31660v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Leveraging In-Context Learning and Retrieval-Augmented Generation for Automatic Question Generation in Educational Domains' (Paper) [chunk: chunk_arxiv_2501_17397v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'CRISS: A Retrieval-Augmented AI Chatbot for Assisting Cancer Registrars' (Paper) [chunk: chunk_arxiv_2609_29075v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Retrieval-Augmented Generation in Industry: An Interview Study on Use Cases, Requirements, Challenges, and Evaluation' (Paper) [chunk: chunk_arxiv_2508_14066v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Blended RAG: Improving RAG (Retriever-Augmented Generation) Accuracy with Semantic Search and Hybrid Query-Based Retrievers' (Paper) [chunk: chunk_arxiv_2404_07220v2_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'IGMiRAG: Intuition-Guided Retrieval-Augmented Generation with Adaptive Mining of In-Depth Memory' (Paper) [chunk: chunk_arxiv_2602_07525v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'How Do LLMs Cite? A Mechanistic Interpretation of Attribution in Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2606_28358v2_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Reconstructing Context: Evaluating Advanced Chunking Strategies for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2504_19754v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'A Collaborative Multi-Agent Approach to Retrieval-Augmented Generation Across Diverse Data' (Paper) [chunk: chunk_arxiv_2412_05838v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'FAIR-RAG: Faithful Adaptive Iterative Refinement for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2510_22344v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Engineering the RAG Stack: A Comprehensive Review of the Architecture and Trust Frameworks for Retrieval-Augmented Generation Systems' (Paper) [chunk: chunk_arxiv_2601_05264v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Automated Literature Review Using NLP Techniques and LLM-Based Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2411_18583v1_000].
```

```
[graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'EVOR: Evolving Retrieval for Code Generation' (Paper) [chunk: chunk_arxiv_2402_12317v2_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 5288.5ms |
| rag.answer_relevancy | 0.197 ❌ |
| rag.context_precision | 0.555 ❌ |
| rag.faithfulness | 0.175 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.133 ❌ |

### Example 9

**Input:**

```
What index type does DPR employ for fast MIPS passage search?
```

**Output:**

```
DPR employs a Lucene BM25 index for fast MIPS passage search [chunk_arxiv_2004_04906_000].
```

**Reference:**

```
Key entities: Dense Passage Retrieval, FAISS. Expected facts: FAISS, HNSW, Flat.
```

**Retrieved context:**

```
[graph] Method Lineage: Dense Passage Retrieval (DPR) -> extends -> Lucene BM25 [chunks: chunk_arxiv_2004_04906_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 12845.6ms |
| rag.answer_relevancy | 0.141 ❌ |
| rag.context_precision | 0.522 ❌ |
| rag.faithfulness | 0.523 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.087 ❌ |

### Example 10

**Input:**

```
What is the dimension of the embedding vectors produced by DPR?
```

**Output:**

```
The provided context does not contain any information about the dimension of the embedding vectors produced by Dense Passage Retrieval (DPR). Therefore, there is insufficient evidence to answer the question.
```

**Reference:**

```
Key entities: Dense Passage Retrieval. Expected facts: 768, dimension.
```

**Retrieved context:**

```
[graph] Method Lineage: Dense Passage Retrieval (DPR) -> extends -> Lucene BM25 [chunks: chunk_arxiv_2004_04906_000].
```

**Scores:**

| Metric | Score |
|---|---|
| latency_ms | 3973.2ms |
| rag.answer_relevancy | 0.995 ✅ |
| rag.context_precision | 0.690 ❌ |
| rag.faithfulness | 0.595 ❌ |
| text_similarity.exact_match | 0.000 ❌ |
| text_similarity.f1 | 0.205 ❌ |
