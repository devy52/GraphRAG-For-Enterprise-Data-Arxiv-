# Phase 31C Evaluation Report: Oracle Control on 16 Failed Questions

**Date**: 2026-10-06 13:39:17 UTC  
**Generator**: Qwen2.5-7B-Instruct (temperature=0.0, identical prompt/validation templates)  
**Evaluator**: EvaluatorV2 (Channel-Strict Accounting, ADR 057)  
**Dataset SHA256**: `88fc85fc1af4200abcfe9530bd8228156b407b8cb04c4c1745472cc080fdcae4`  

---

## 1. Executive Summary

| Metric | Run 3B Baseline (16 Failures) | Phase 31C Oracle Control | Absolute Delta |
| :--- | :---: | :---: | :---: |
| **Mean Fact Score** | **0.3958** | **0.8646** | **+0.4688** |
| **Strict Passes (Fact Score >= 0.70)** | **0/16 (0.0%)** | **13/16 (81.2%)** | **+13** |

### Categorization Breakdown

- **Fail -> Pass**: 3/16 (18.8%)
- **Fail -> Fail**: 1/16 (6.2%)
- **Partial -> Better**: 10/16 (62.5%)
- **Partial -> Same**: 2/16 (12.5%)

---

## 2. Per-Question Results Table

| ID | Hop Type | Run 3B Fact | Oracle Fact | Delta | Interpretation |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `q_1hop_02` | EvalHopTypeV2.ONE_HOP | 0.0000 | **1.0000** | +1.0000 | Fail -> Pass (Retrieval/Context Deficiency) |
| `q_1hop_03` | EvalHopTypeV2.ONE_HOP | 0.0000 | **1.0000** | +1.0000 | Fail -> Pass (Retrieval/Context Deficiency) |
| `q_2hop_03` | EvalHopTypeV2.TWO_HOP | 0.0000 | **0.0000** | +0.0000 | Fail -> Fail (Generator / Evaluator / Formulation Issue) |
| `q_2hop_06` | EvalHopTypeV2.TWO_HOP | 0.0000 | **1.0000** | +1.0000 | Fail -> Pass (Retrieval/Context Deficiency) |
| `q_2hop_07` | EvalHopTypeV2.TWO_HOP | 0.5000 | **1.0000** | +0.5000 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_2hop_10` | EvalHopTypeV2.TWO_HOP | 0.5000 | **0.5000** | +0.0000 | Partial -> Same (Downstream Reasoning / Evidence Formulation Issue) |
| `q_3hop_03` | EvalHopTypeV2.THREE_HOP | 0.3333 | **1.0000** | +0.6667 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_3hop_05` | EvalHopTypeV2.THREE_HOP | 0.6667 | **0.3333** | -0.3334 | Partial -> Same (Downstream Reasoning / Evidence Formulation Issue) |
| `q_3hop_06` | EvalHopTypeV2.THREE_HOP | 0.6667 | **1.0000** | +0.3333 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_3hop_08` | EvalHopTypeV2.THREE_HOP | 0.6667 | **1.0000** | +0.3333 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_3hop_09` | EvalHopTypeV2.THREE_HOP | 0.3333 | **1.0000** | +0.6667 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_3hop_10` | EvalHopTypeV2.THREE_HOP | 0.6667 | **1.0000** | +0.3333 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_agg_01` | EvalHopTypeV2.AGGREGATION | 0.5000 | **1.0000** | +0.5000 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_agg_02` | EvalHopTypeV2.AGGREGATION | 0.5000 | **1.0000** | +0.5000 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_agg_04` | EvalHopTypeV2.AGGREGATION | 0.5000 | **1.0000** | +0.5000 | Partial -> Better (Retrieval Deficiency Contributed Materially) |
| `q_agg_06` | EvalHopTypeV2.AGGREGATION | 0.5000 | **1.0000** | +0.5000 | Partial -> Better (Retrieval Deficiency Contributed Materially) |

---

## 3. Detailed Case Analysis

### `q_1hop_02` (EvalHopTypeV2.ONE_HOP)
**Question**: What benchmark is proposed in 'When to use Graphs in RAG' to evaluate GraphRAG models?  
**Run 3B Score**: 0.0000 | **Oracle Score**: 1.0000  
**Outcome**: Fail -> Pass (Retrieval/Context Deficiency)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to determine the benchmark proposed in 'When to use Graphs in RAG' to evaluate GraphRAG models.

**Oracle Generated Answer**:
> GraphRAG-Bench is proposed in 'When to use Graphs in RAG' to evaluate GraphRAG models [chunk_arxiv_2506_05690v3_000].

---

### `q_1hop_03` (EvalHopTypeV2.ONE_HOP)
**Question**: What dataset was introduced in 'From RAG to Agentic RAG' for faithful Islamic question answering?  
**Run 3B Score**: 0.0000 | **Oracle Score**: 1.0000  
**Outcome**: Fail -> Pass (Retrieval/Context Deficiency)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to determine the dataset introduced in 'From RAG to Agentic RAG' for faithful Islamic question answering.

**Oracle Generated Answer**:
> IslamicFaithQA was introduced in 'From RAG to Agentic RAG for Faithful Islamic Question Answering' [chunk_arxiv_2601_07528v2_000].

---

### `q_2hop_03` (EvalHopTypeV2.TWO_HOP)
**Question**: What three agentic components are ablated in Sheroz Shaikh's study on multi-hop QA?  
**Run 3B Score**: 0.0000 | **Oracle Score**: 0.0000  
**Outcome**: Fail -> Fail (Generator / Evaluator / Formulation Issue)  

**Run 3B Generated Answer**:
> Unfortunately, the provided context does not contain sufficient information to answer the question about the three agentic components ablated in Sheroz Shaikh's study on multi-hop QA. The context mentions various methods and techniques used in the study, such as dense-retrieval, BM25, and RAG, but it does not explicitly mention the three agentic components that are ablated.

**Oracle Generated Answer**:
> Unfortunately, there is insufficient evidence in the provided context to determine the specific three agentic components ablated in Sheroz Shaikh's study on multi-hop QA. The passage only mentions a controlled ablation study of a full agentic RAG pipeline, but it does not specify the components being ablated. [chunk_arxiv_2606_21553v1_000]

---

### `q_2hop_06` (EvalHopTypeV2.TWO_HOP)
**Question**: What dual failure modes does Yizhuo Ma et al. identify when knowledge graphs are constructed by LLMs for GraphRAG?  
**Run 3B Score**: 0.0000 | **Oracle Score**: 1.0000  
**Outcome**: Fail -> Pass (Retrieval/Context Deficiency)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to identify the dual failure modes that Yizhuo Ma et al. identify when knowledge graphs are constructed by LLMs for GraphRAG.

**Oracle Generated Answer**:
> Yizhuo Ma et al. identify two recurring knowledge graph issue modes when constructed by LLMs for GraphRAG: spurious noise and incomplete information [chunk_arxiv_2603_14828v2_000].

---

### `q_2hop_07` (EvalHopTypeV2.TWO_HOP)
**Question**: What parameter size of language models does Kotoge et al. study for distillation-guided agentic search?  
**Run 3B Score**: 0.5000 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to determine the parameter size of language models studied by Kotoge et al. for distillation-guided agentic search.

**Oracle Generated Answer**:
> The compact language models studied by Kotoge et al. have a parameter size of 0.5--1B [chunk_arxiv_2508_20324v4_000].

---

### `q_2hop_10` (EvalHopTypeV2.TWO_HOP)
**Question**: Why do traditional GraphRAG methods fail on temporal reasoning tasks according to DyG-RAG?  
**Run 3B Score**: 0.5000 | **Oracle Score**: 0.5000  
**Outcome**: Partial -> Same (Downstream Reasoning / Evidence Formulation Issue)  

**Run 3B Generated Answer**:
> Traditional GraphRAG methods struggle with temporal reasoning due to their inability to model the evolving structure and order of real-world events [chunk_arxiv_2507_13396v1_000].

**Oracle Generated Answer**:
> Traditional Graph RAG methods struggle with temporal reasoning because they are unable to model the evolving structure and order of real-world events [chunk_arxiv_2507_13396v1_000].

---

### `q_3hop_03` (EvalHopTypeV2.THREE_HOP)
**Question**: How does Dissecting Agentic RAG isolate the individual performance contributions of query decomposition and adaptive retrieval?  
**Run 3B Score**: 0.3333 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> Unfortunately, the provided context does not contain sufficient information to answer the question about how Dissecting Agentic RAG isolates the individual performance contributions of query decomposition and adaptive retrieval. The context only mentions the use of Qwen2.5-7B-Instruct method and HotpotQA distractor development set in Dissecting Agentic RAG, but it does not provide any information about the isolation of individual performance contributions of query decomposition and adaptive retrieval.

**Oracle Generated Answer**:
> According to the paper 'Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model', query decomposition and cross-encoder reranking each contribute statistically significant but smaller gains [chunk_arxiv_2606_21553v1_001].

---

### `q_3hop_05` (EvalHopTypeV2.THREE_HOP)
**Question**: How does the comparative study 'RAG vs. GraphRAG' analyze performance trade-offs on structured knowledge graph data?  
**Run 3B Score**: 0.6667 | **Oracle Score**: 0.3333  
**Outcome**: Partial -> Same (Downstream Reasoning / Evidence Formulation Issue)  

**Run 3B Generated Answer**:
> The comparative study 'RAG vs. GraphRAG: A Systematic Evaluation and Key Insights' does not provide explicit analysis of performance trade-offs on structured knowledge graph data. However, it does present a comprehensive benchmark study comparing RAG and GraphRAG on established text-based tasks, including question answering and query-based summarization [chunk_arxiv_2502_11371v3_001]. The study highlights the distinct strengths of RAG and GraphRAG across different tasks and evaluation perspectives, but it does not specifically address structured knowledge graph data.

**Oracle Generated Answer**:
> There is insufficient evidence in the provided context to determine how the comparative study 'RAG vs. GraphRAG' analyzes performance trade-offs on structured knowledge graph data.

---

### `q_3hop_06` (EvalHopTypeV2.THREE_HOP)
**Question**: How do imperfect LLM-generated knowledge graphs cause retrieval drift in multi-hop GraphRAG according to Yizhuo Ma et al.?  
**Run 3B Score**: 0.6667 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to answer the question about how imperfect LLM-generated knowledge graphs cause retrieval drift in multi-hop GraphRAG according to Yizhuo Ma et al.

**Oracle Generated Answer**:
> According to the paper by Yizhuo Ma et al., imperfect LLM-generated knowledge graphs cause retrieval drift in multi-hop GraphRAG by inducing spurious noise, which leads to retrieval drift toward plausible but unsupported triples [chunk_arxiv_2603_14828v2_000].

---

### `q_3hop_08` (EvalHopTypeV2.THREE_HOP)
**Question**: How does the survey by Aditi Singh et al. define the core architectural transition from standard RAG to Agentic RAG?  
**Run 3B Score**: 0.6667 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> The survey by Aditi Singh et al. defines the core architectural transition from standard RAG to Agentic RAG as embedding autonomous AI agents into the RAG pipeline, which leverage agentic design patterns such as reflection, planning, tool use, and multi-agent collaboration to dynamically manage retrieval strategies, iteratively refine contextual understanding, and adapt workflows [chunk_arxiv_2501_09136v4_001].

**Oracle Generated Answer**:
> Unfortunately, the provided context does not contain sufficient information to answer the question about how the survey by Aditi Singh et al. defines the core architectural transition from standard RAG to Agentic RAG. The context only provides information about the limitations of traditional RAG systems and the benefits of Agentic RAG systems, but it does not mention the specific survey by Aditi Singh et al. or the definition of the core architectural transition.

---

### `q_3hop_09` (EvalHopTypeV2.THREE_HOP)
**Question**: How does RAGU's multi-step graph construction pipeline mitigate entity noise compared to single-pass extraction?  
**Run 3B Score**: 0.3333 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to answer how RAGU's multi-step graph construction pipeline mitigates entity noise compared to single-pass extraction.

**Oracle Generated Answer**:
> RAGU's multi-step graph construction pipeline mitigates entity noise by separating extraction from consolidation, which includes two-stage typed extraction, DBSCAN-backed deduplication, LLM summarization, and Leiden community detection [chunk_arxiv_2607_11683v1_000].

---

### `q_3hop_10` (EvalHopTypeV2.THREE_HOP)
**Question**: How does MetaRAG align agent belief and action policies during iterative search decisions?  
**Run 3B Score**: 0.6667 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to determine how MetaRAG aligns agent belief and action policies during iterative search decisions.

**Oracle Generated Answer**:
> MetaRAG aligns agent belief and action policies during iterative search decisions through the use of Verify-first Action Generation and Internal Belief Probing. Verify-first Action Generation elicits an explicit verification process before each actual action, allowing the agent to verify its own belief about the sufficiency of the current evidence [chunk_arxiv_2608_24214v1_000]. Internal Belief Probing estimates the policy model's own answerability belief from the same question-history context, enabling the agent to make informed decisions about when to continue searching and when to answer [chunk_arxiv_2608_24214v1_000].

---

### `q_agg_01` (EvalHopTypeV2.AGGREGATION)
**Question**: Compare the primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA.  
**Run 3B Score**: 0.5000 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence to compare the primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA, as the provided context only discusses GraphRAG-Bench and does not mention IslamicFaithQA.

**Oracle Generated Answer**:
> The primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA differ. GraphRAG-Bench is designed to evaluate GraphRAG models on both hierarchical knowledge retrieval and deep contextual reasoning [chunk_arxiv_2506_05690v3_000]. In contrast, IslamicFaithQA focuses on measuring hallucination and abstention in Islamic question answering, with a 3,810-item bilingual (Arabic/English) generative benchmark [chunk_arxiv_2601_07528v2_000]. There is insufficient evidence to establish a direct comparison between the two objectives.

---

### `q_agg_02` (EvalHopTypeV2.AGGREGATION)
**Question**: What shared limitations of vanilla RAG are identified in both GRAG and 'When to use Graphs in RAG'?  
**Run 3B Score**: 0.5000 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence in the provided context to identify shared limitations of vanilla RAG that are mentioned in both GRAG and 'When to use Graphs in RAG'. The context only mentions limitations of vanilla RAG in the context of GraphSearch [chunk_arxiv_2509_22009v2_000], but does not provide information about 'When to use Graphs in RAG'.

**Oracle Generated Answer**:
> Naive Retrieval-Augmented Generation (RAG) falls short in handling networked documents, which are popular in many applications such as citation graphs, social media, and knowledge graphs [chunk_arxiv_2405_16506v3_000]. This limitation is also acknowledged in the context of GraphRAG, which underperforms vanilla RAG on many real-world tasks [chunk_arxiv_2506_05690v3_000].

---

### `q_agg_04` (EvalHopTypeV2.AGGREGATION)
**Question**: Compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware.  
**Run 3B Score**: 0.5000 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> There is insufficient evidence to compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware.

**Oracle Generated Answer**:
> HeRo and Kotoge et al. employ different efficiency strategies for running Agentic RAG on resource-constrained hardware. HeRo is a heterogeneous-aware framework that aims to enhance LLM-based applications by adapting to the strong accelerator affinity, shape sensitivity, and shared-memory bandwidth contention of mobile SoCs [chunk_arxiv_2603_01661v2_000]. On the other hand, Kotoge et al. propose Distillation-Guided Policy Optimization (DGPO) to elicit agentic RAG behaviors from compact language models, which are particularly challenging to train due to poor initial performance and sparse rewards [chunk_arxiv_2508_20324v4_000]. 

While HeRo focuses on optimizing the execution flow of agentic RAG on heterogeneous SoCs, Kotoge et al. aim to improve the agentic behavior of compact language models through teacher demonstrations and continuous guidance during policy optimization. The two approaches address different aspects of efficiency in Agentic RAG on resource-constrained hardware, with HeRo targeting the hardware-level optimization and Kotoge et al. focusing on the model-level optimization.

---

### `q_agg_06` (EvalHopTypeV2.AGGREGATION)
**Question**: What complementary context optimization approaches are proposed by ACE-GraphRAG and Empowering GraphRAG?  
**Run 3B Score**: 0.5000 | **Oracle Score**: 1.0000  
**Outcome**: Partial -> Better (Retrieval Deficiency Contributed Materially)  

**Run 3B Generated Answer**:
> The context optimization approaches proposed by ACE-GraphRAG are gap-aware refinement, retrieval branches, and task-conditioned adaptation [chunk_arxiv_2608_01269v2_000].

**Oracle Generated Answer**:
> ACE-GraphRAG proposes an inference-time context policy layer that supplements and adapts the initial context for generation, formulating context construction as a policy over gap-aware refinement, retrieval branches, and task-conditioned adaptation [chunk_arxiv_2608_01269v2_000].

Empowering GraphRAG proposes a complementary approach, GraphRAG-FI (Filtering and Integration), which consists of GraphRAG-Filtering and GraphRAG-Integration. GraphRAG-Filtering employs a two-stage filtering mechanism to refine retrieved information [chunk_arxiv_2503_13804v1_000].

---
