# Spot-Check Samples for Manual Verification

**5 randomly selected examples** for human review.
Compare the system answer and retrieved context against the reference
to verify whether the computed scores make sense.

## Sample 1: `q_1hop_02` (1-hop)

**Question**: What primary model architecture is proposed in the RAG paper?

**Reference**: Key entities: Retrieval-Augmented Generation. Expected facts: RAG-Sequence, RAG-Token, generator, retriever.

**System Answer**:
```
The primary model architecture proposed is a hierarchical heterogeneous hypergraph that aligns multi‑granular knowledge and incorporates deductive pathways to simulate realistic memory structures, as introduced in the IGMiRAG framework. [chunk_arxiv_2602_07525v1_000]
```

**Retrieved Context** (first 3 passages):
  1. [retrieved] [chunk_arxiv_2507_06956v1_000] Large language models (LLMs) are very costly and inefficient to update with new information. To address this limitation, retrieval-augmented generation (RAG)...
  2. [retrieved] [chunk_arxiv_2605_15790v1_001] s efficient optimization through problem decomposition. Experimental results show that our method effectively mitigates generation bias while preserving rele...
  3. [retrieved] [chunk_arxiv_2601_14546v1_002] ral Questions (NQ) dataset show that combining predictors from multiple feature categories yields the most accurate estimates of RAG performance....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.1000 |
| `rag.context_precision` | 0.2000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.2000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.0000 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 2: `q_1hop_01` (1-hop)

**Question**: Who are the primary authors of the Dense Passage Retrieval paper?

**Reference**: Key entities: Dense Passage Retrieval, Patrick Lewis. Expected facts: Vladimir Karpukhin, Barlas Oguz, Patrick Lewis.

**System Answer**:
```
The primary authors of the Dense Passage Retrieval paper are Vladimir Karpukhin [chunk_arxiv_2004_04906_000], Barlas Oguz [chunk_arxiv_2004_04906_000], and Patrick Lewis [chunk_arxiv_2004_04906_000].
```

**Retrieved Context** (first 3 passages):
  1. [graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Vladimir Karpukhin [chunk: chunk_arxiv_2004_04906_000]....
  2. [graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Barlas Oguz [chunk: chunk_arxiv_2004_04906_000]....
  3. [graph] Paper 'Dense Passage Retrieval for Open-Domain Question Answering' was authored by Patrick Lewis [chunk: chunk_arxiv_2004_04906_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.7500 |
| `rag.context_precision` | 0.6500 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 1.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.5143 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 3: `q_1hop_05` (1-hop)

**Question**: Who authored the ColBERT late-interaction retrieval paper?

**Reference**: Key entities: ColBERT. Expected facts: Omar Khattab, Matei Zaharia.

**System Answer**:
```
Omar Khattab and Matei Zaharia authored the ColBERT late-interaction retrieval paper [chunk_arxiv_2004_12832_000][chunk_arxiv_2004_12832_000].
```

**Retrieved Context** (first 2 passages):
  1. [graph] Paper 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT' was authored by Omar Khattab [chunk: chunk_arxiv_2004_12832_000]....
  2. [graph] Paper 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT' was authored by Matei Zaharia [chunk: chunk_arxiv_2004_12832_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 1.0000 |
| `rag.context_precision` | 1.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 1.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.4348 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 4: `q_1hop_10` (1-hop)

**Question**: What is the dimension of the embedding vectors produced by DPR?

**Reference**: Key entities: Dense Passage Retrieval. Expected facts: 768, dimension.

**System Answer**:
```
DPR uses a BERT‑base encoder backbone that produces embedding vectors of dimension 768 [chunk_arxiv_2004_04906_000].
```

**Retrieved Context** (first 3 passages):
  1. [retrieved] [chunk_arxiv_2004_04906_000] Open-domain question answering relies on efficient passage retrieval to select candidate contexts. We show that retrieval can be practically implemented using ...
  2. [retrieved] [chunk_arxiv_2502_00306v2_001] RAG datastore. By crafting natural-text queries that are answerable only with the target document's presence, our approach demonstrates successful inference ...
  3. [retrieved] [chunk_arxiv_2004_04906_extra_0] Dense Passage Retrieval (DPR) pairs with generator models such as BART and T5 for open-domain question answering. Methods extending DPR's dual-encoder arch...

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 1.0000 |
| `rag.context_precision` | 0.2000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1667 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 5: `q_1hop_07` (1-hop)

**Question**: What encoder backbone was used in the original DPR experiments?

**Reference**: Key entities: Dense Passage Retrieval, BERT. Expected facts: BERT, BERT-base.

**System Answer**:
```
The provided context does not contain any information about the encoder backbone used in the original DPR experiments. Therefore, there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 3 passages):
  1. [graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'ColBERT' (Method) [chunk: chunk_arxiv_2004_04906_extra_0]....
  2. [graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'RocketQA' (Method) [chunk: chunk_arxiv_2004_04906_extra_0]....
  3. [graph] Entity 'Dense Passage Retrieval (DPR)' -[:EXTENDS]- 'BART' (Method) [chunk: chunk_arxiv_2004_04906_extra_0]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.1500 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.0000 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---
