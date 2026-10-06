# Spot-Check Samples for Manual Verification

**5 randomly selected examples** for human review.
Compare the system answer and retrieved context against the reference
to verify whether the computed scores make sense.

## Sample 1: `q_2hop_02` (2-hop)

**Question**: What retrieval methods extend the dual-encoder architecture introduced by DPR?

**Reference**: Key entities: Dense Passage Retrieval. Expected facts: ANCE, RocketQA, ColBERT.

**System Answer**:
```
The provided context does not contain any information about retrieval methods that extend the dual-encoder architecture introduced by Dense Passage Retrieval (DPR). Therefore, there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 1 passages):
  1. [graph] Method Lineage: Dense Passage Retrieval (DPR) -> extends -> Lucene BM25 [chunks: chunk_arxiv_2004_04906_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.2000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1429 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 2: `q_2hop_01` (2-hop)

**Question**: Which researchers co-authored papers with Patrick Lewis on retrieval-augmented models?

**Reference**: Key entities: Patrick Lewis. Expected facts: Ethan Perez, Aleksandra Piktus, Sebastian Riedel.

**System Answer**:
```
Patrick Lewis co‑authored retrieval‑augmented model papers with Vladimir Karpukhin [chunk_arxiv_2004_04906_000], Barlas Oguz [chunk_arxiv_2004_04906_000], Sebastian Riedel [chunk_arxiv_2005_11401_000], and Douwe Kiela [chunk_arxiv_2005_11401_000].
```

**Retrieved Context** (first 3 passages):
  1. [graph] Patrick Lewis co-authored paper 'Dense Passage Retrieval for Open-Domain Question Answering' with Vladimir Karpukhin [chunk: chunk_arxiv_2004_04906_000]....
  2. [graph] Patrick Lewis co-authored paper 'Dense Passage Retrieval for Open-Domain Question Answering' with Barlas Oguz [chunk: chunk_arxiv_2004_04906_000]....
  3. [graph] Patrick Lewis co-authored paper 'mKG-RAG: Leveraging Multimodal Knowledge Graphs in Retrieval-Augmented Generation for Knowledge-intensive VQA' with Sebastian Riedel [chunk: chunk_arxiv_2005_1...

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 1.0000 |
| `rag.context_precision` | 1.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 1.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.2353 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 3: `q_2hop_05` (2-hop)

**Question**: Which institutions published research co-authored by Omar Khattab and Matei Zaharia?

**Reference**: Key entities: Omar Khattab, Matei Zaharia. Expected facts: Stanford, Stanford University.

**System Answer**:
```
The provided context only indicates that Omar Khattab and Matei Zaharia co‑authored the paper “ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT” [chunk: chunk_arxiv_2004_12832_000]. No information about the institutions that published this research is included in the given context. Therefore, the corpus lacks sufficient evidence to determine which institutions published their joint work.
```

**Retrieved Context** (first 1 passages):
  1. [graph] Matei Zaharia co-authored paper 'ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT' with Omar Khattab [chunk: chunk_arxiv_2004_12832_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.8000 |
| `rag.context_precision` | 0.3000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 1.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1159 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 4: `q_2hop_10` (2-hop)

**Question**: What methods adapt late-interaction token scoring to dense passage representations?

**Reference**: Key entities: ColBERT, Dense Passage Retrieval. Expected facts: ColBERTv2, PLAID, late interaction.

**System Answer**:
```
The provided context does not contain any information about methods that adapt late-interaction token scoring to dense passage representations, so there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 3 passages):
  1. [graph] Method Lineage: Large Language Model GPT-3.5-turbo -> extends -> EVOR [chunks: chunk_arxiv_2411_18583v1_001]....
  2. [graph] Method Lineage: transformer model -> extends -> EVOR [chunks: chunk_arxiv_2411_18583v1_001]....
  3. [graph] Method Lineage: Large Language Model GPT-3.5-turbo -> extends -> transformer model -> extends -> EVOR [chunks: chunk_arxiv_2411_18583v1_001, chunk_arxiv_2411_18583v1_001]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.0000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1951 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---

## Sample 5: `q_2hop_07` (2-hop)

**Question**: What methods use hard negative mining techniques derived from DPR's BM25 negatives?

**Reference**: Key entities: Dense Passage Retrieval, BM25. Expected facts: ANCE, RocketQA, hard negatives.

**System Answer**:
```
The provided context does not contain any information about hard negative mining techniques derived from DPR’s BM25 negatives, so there is insufficient evidence to answer the question.
```

**Retrieved Context** (first 3 passages):
  1. [graph] Entity 'BM25' -[:COMPARED_WITH]- 'PathOCL' (Method) [chunk: chunk_arxiv_2505_13129v1_001]....
  2. [graph] Entity 'BM25' -[:USES_METHOD]- 'Optimizing Retrieval Augmented Generation for Object Constraint Language' (Paper) [chunk: chunk_arxiv_2505_13129v1_001]....
  3. [graph] Entity 'BM25' -[:USES_METHOD]- 'Optimizing Retrieval Augmented Generation for Object Constraint Language' (Paper) [chunk: chunk_arxiv_2505_13129v1_000]....

**Computed Scores**:

| Metric | Score |
|---|---|
| `rag.answer_relevancy` | 0.0000 |
| `rag.context_precision` | 0.2000 |
| `rag.faithfulness` | 1.0000 |
| `rag.hallucination_rate` | 0.0000 |
| `retrieval.chunk_utilization` | 0.0000 |
| `text_similarity.exact_match` | 0.0000 |
| `text_similarity.f1` | 0.1500 |

**Manual Check**: Does the system answer address the question?
Does it contain the expected keywords from the reference?
Is the F1 score consistent with what you'd expect from the overlap?

---
