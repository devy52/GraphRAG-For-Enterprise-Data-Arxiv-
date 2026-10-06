# Phase 31D Diagnostic Report: Edge-Case Failure Classification

**Date**: 2026-10-06  
**Status**: Completed  
**Objective**: Audit the 3 non-passing Oracle control cases (`q_2hop_03`, `q_2hop_10`, `q_3hop_05`) to establish whether failures stem from genuine generator limitations, annotation omissions, evaluator semantics, or question/source premise mismatches.  
**Benchmark Invariant**: The frozen benchmark (`data/benchmark_v2_dataset.jsonl`) remains 100% UNCHANGED during this diagnostic.

---

## 1. Summary of Classifications

| Question ID | Hop Type | Run 3B Score | Oracle Score | Final Classification | Primary Defect Mechanism |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `q_2hop_03` | 2-hop | 0.0000 | 0.0000 | **ANNOTATION DEFECT** | Gold evidence omitted chunk 001; chunk 000 introduces the pipeline but does not enumerate the 3 ablated components. Generator faithfully refused. |
| `q_2hop_10` | 2-hop | 0.5000 | 0.5000 | **ANNOTATION DEFECT** | Source chunk does not contain the phrase "static graphs" (it states "inability to model evolving structure"). Fact 1 requires an extrinsic concept not grounded in the source passage. |
| `q_3hop_05` | 3-hop | 0.6667 | 0.3333 | **QUESTION/SOURCE MISMATCH** | Question asks how the paper analyzes trade-offs on *structured knowledge graph data*, but the paper explicitly tested *text-based tasks*. Generator faithfully rejected the false premise; Run 3B scored higher only through serendipitous partial token overlap. |

---

## 2. Deep Case-by-Case Audit

### Case 1: `q_2hop_03` (2-Hop)
- **Question**: *"What three agentic components are ablated in Sheroz Shaikh's study on multi-hop QA?"*
- **Reference Answer**: *"The study dissects agentic RAG by ablating iterative reasoning loops, query decomposition, and adaptive retrieval on a local 7B model."*
- **Required Facts**:
  - `q2hop3_f1`: Iterative reasoning loops (weight: 1.0)
  - `q2hop3_f2`: Query decomposition and adaptive retrieval (weight: 1.0)
- **Supplied Gold Evidence**: `chunk_arxiv_2606_21553v1_000` (Abstract Part 1).
- **Source Chunk Text**:
  > *"Agentic retrieval-augmented generation (RAG) systems combine iterative reasoning loops, query decomposition, and adaptive retrieval to tackle multi-hop question answering. However, the contribution of each component remains poorly understood, particularly under resource-constrained settings using only local language models. Many agentic designs add adaptive retrieval routing and deeper retrieval loops on the assumption that the added complexity helps. To test whether it does, we run a controlled ablation study of a full agentic RAG pipeline evaluated on 5,000 questions from the HotpotQA distractor development set using a local 7B parameter model (Qwen2.5-7B-Instruct)."*
- **Omitted Corpus Text (`chunk_arxiv_2606_21553v1_001`)**:
  > *"Across eight ablation conditions, we find that: (1) fixed hybrid retrieval via reciprocal rank fusion consistently outperforms rule-based adaptive routing... (2) two retrieval iterations over the decomposed sub-questions capture 95% of the gains of five... and (3) query decomposition and cross-encoder reranking each contribute statistically significant but smaller gains..."*
- **Findings**:
  Chunk 000 describes general agentic RAG concepts and announces that an ablation study was performed, but does not state which components were ablated in the study. The generator strictly adhered to the grounded context and refused: *"The passage only mentions a controlled ablation study of a full agentic RAG pipeline, but it does not specify the components being ablated."* When both chunks 000 and 001 are supplied (as in `q_3hop_03`), the model answers with a 1.0000 fact score.
- **Classification**: **ANNOTATION DEFECT** (Omitted supporting chunk in gold annotation).

---

### Case 2: `q_2hop_10` (2-Hop)
- **Question**: *"Why do traditional GraphRAG methods fail on temporal reasoning tasks according to DyG-RAG?"*
- **Reference Answer**: *"Traditional GraphRAG methods fail on temporal reasoning because they rely on static graphs and are unable to model the temporal evolution of events and facts."*
- **Required Facts**:
  - `q2hop10_f1`: "Relies on static graphs" (weight: 1.0, aliases: `['static graphs', 'static graph', 'static']`)
  - `q2hop10_f2`: "Inability to model temporal evolution" (weight: 1.0, aliases: `['temporal reasoning', 'temporal evolution', 'evolution of facts', 'temporal']`)
- **Supplied Gold Evidence**: `chunk_arxiv_2507_13396v1_000` (Abstract).
- **Source Chunk Text**:
  > *"Graph Retrieval-Augmented Generation has emerged as a powerful paradigm for grounding large language models with external structured knowledge. However, existing Graph RAG methods struggle with temporal reasoning, due to their inability to model the evolving structure and order of real-world events. In this work, we introduce DyG-RAG, a novel event-centric dynamic graph retrieval-augmented generation framework..."*
- **Findings**:
  The source chunk text literally states that traditional GraphRAG struggles *"due to their inability to model the evolving structure and order of real-world events"*. The phrase *"static graphs"* never appears anywhere in the chunk. The generator generated an exact synthesis: *"Traditional Graph RAG methods struggle with temporal reasoning because they are unable to model the evolving structure and order of real-world events."* Fact 2 was marked entailed (1.0), while Fact 1 was marked unsupported (0.0) because the required fact demanded an extrinsic abstraction not stated in the source text.
- **Classification**: **ANNOTATION DEFECT** (Extrinsic concept required that is absent from source text).

---

### Case 3: `q_3hop_05` (3-Hop)
- **Question**: *"How does the comparative study 'RAG vs. GraphRAG' analyze performance trade-offs on structured knowledge graph data?"*
- **Reference Answer**: *"The study performs a systematic evaluation comparing standard text RAG and GraphRAG across structured knowledge graphs, identifying scenarios where relational graph indexing outperforms dense passage retrieval."*
- **Required Facts**:
  - `q3hop5_f1`: Systematic evaluation of RAG versus GraphRAG
  - `q3hop5_f2`: Evaluates structured data and knowledge graphs
  - `q3hop5_f3`: Identifies trade-offs between text retrieval and graph indexing
- **Supplied Gold Evidence**: `chunk_arxiv_2502_11371v3_000` & `chunk_arxiv_2502_11371v3_001` (Abstract).
- **Source Chunk Text**:
  > *"...In this paper, we present a comprehensive benchmark study comparing RAG and GraphRAG on established text-based tasks, including question answering and query-based summarization... Our results highlight the distinct strengths of RAG and GraphRAG across different tasks and evaluation perspectives."*
- **Findings**:
  The paper investigated RAG vs GraphRAG on **text-based tasks** by converting unstructured text to graph representations; it explicitly did not evaluate structured knowledge graph datasets.
  - In Run 3B (partial context), the generator produced a conversational answer discussing the paper and noting it evaluated text-based tasks, coincidentally matching aliases for `q3hop5_f1` and `q3hop5_f3` (fact score 0.6667).
  - In Oracle (complete context), the generator observed the complete text, recognized that the premise of the question was unsupported, and faithfully refused: *"There is insufficient evidence in the provided context to determine how the comparative study 'RAG vs. GraphRAG' analyzes performance trade-offs on structured knowledge graph data."* This dropped the score to 0.3333 because the reference answer had asserted a false premise.
- **Classification**: **QUESTION/SOURCE MISMATCH** (Question premise directly contradicts source findings).

---

## 3. Methodological Conclusion

1. **Zero Genuine Generator Failures**: Across all 16 Run 3B failures:
   - 13/16 (81.3%) are strictly resolved when substantive evidence is supplied.
   - 2/16 are annotation formulation defects (`q_2hop_03`, `q_2hop_10`).
   - 1/16 is a question/source premise mismatch (`q_3hop_05`).
   - **0/16 are attributable to 7B generator reasoning capacity limits.**
2. **Frozen Benchmark Integrity**: The benchmark dataset remains strictly untouched. No questions, required facts, or annotations were modified during Phase 31D.
3. **Implication for Phase 32**: The entire remaining error mass in the enterprise GraphRAG pipeline is driven by **retrieval evidence availability** (substantive recall = 0.2821). Phase 32 must focus purely on multi-hop retrieval expansion.
