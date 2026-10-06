# Spot-Check Samples for Manual Verification

**5 randomly selected examples** for human review.
Compare the system answer and retrieved context against the reference
to verify whether the computed scores make sense.

## Sample 1: `q_oos_01` (out-of-scope)

**Question**: What is the chemical mechanism of photosynthesis in C4 plants?

**Reference**: I do not have sufficient evidence in the retrieved corpus to answer this question.

**System Answer**:
```
The provided context does not contain any information about the chemical mechanism of photosynthesis in C4 plants, so there is insufficient evidence to answer the question.
```

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.3500 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 2: `q_1hop_08` (1-hop)

**Question**: What generator model is paired with the DPR retriever in the RAG paper?

**Reference**: Key entities: Retrieval-Augmented Generation, BART. Expected facts: BART, BART-large.

**System Answer**:
```
The provided context does not contain any details about the generator model used alongside the DPR retriever in the RAG paper; it only lists paper titles associated with retrieval-augmented generation. Therefore, there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 3 passages):
  1. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks' (Paper) [chunk: chunk_arxiv_2005_11401_000]....
  2. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Fairness-Aware Retrieval Optimization for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2605_15790v1_000]....
  3. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Predicting Retrieval Utility and Answer Quality in Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2601_14546v1_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.8500 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0800 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1176 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 3: `q_1hop_02` (1-hop)

**Question**: What primary model architecture is proposed in the RAG paper?

**Reference**: Key entities: Retrieval-Augmented Generation. Expected facts: RAG-Sequence, RAG-Token, generator, retriever.

**System Answer**:
```
The primary model architecture proposed in the RAG paper is a hierarchical heterogeneous hypergraph that aligns multi‑granular knowledge and incorporates deductive pathways to simulate realistic memory structures [chunk_arxiv_2602_07525v1_000].
```

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.8500 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 0.0000 |
| `rag.hallucination_rate` | 1.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.0476 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 4: `q_oos_08` (out-of-scope)

**Question**: How do internal combustion engines compare to electric motor drivetrains?

**Reference**: I do not have sufficient evidence in the retrieved corpus to answer this question.

**System Answer**:
```
The provided context does not contain any information about internal combustion engines or electric motor drivetrains, so there is insufficient evidence to answer the question.
```

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.3077 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 5: `q_2hop_08` (2-hop)

**Question**: Who are the common collaborators between the authors of RAG and the authors of FiD?

**Reference**: Key entities: Retrieval-Augmented Generation, Fusion-in-Decoder. Expected facts: Gautier Izacard, Edouard Grave, Sebastian Riedel.

**System Answer**:
```
The corpus does not contain any information about the authors of FiD or about common collaborators between RAG and FiD authors, so there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 3 passages):
  1. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks' (Paper) [chunk: chunk_arxiv_2005_11401_000]....
  2. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Fairness-Aware Retrieval Optimization for Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2605_15790v1_000]....
  3. [graph] Entity 'retrieval-augmented generation (RAG)' -[:HAS_TOPIC]- 'Predicting Retrieval Utility and Answer Quality in Retrieval-Augmented Generation' (Paper) [chunk: chunk_arxiv_2601_14546v1_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.8500 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.0000 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---
