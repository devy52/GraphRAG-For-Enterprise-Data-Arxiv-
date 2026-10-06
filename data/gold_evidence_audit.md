# Gold Evidence Audit: Candidate Insufficiencies (G1 vs. G2)

[← README](../README.md) | [PRD](../Docs/PRD.md) | [TRD](../Docs/TRD.md) | [Design](../Docs/DESIGN.md) | [Architecture](../Docs/ARCHITECTURE.md) | [Flows](../Docs/FLOWS.md) | [Codebase Map](../Docs/CODEBASE_MAP.md) | [Decisions](../Docs/DECISIONS.md) | [Tasks](../Docs/TASKS.md)

---

## Executive Summary

During the Oracle (Gold Context → LLM) ablation baseline analysis, 5 questions scored 0.0 or exhibited abstentions due to potential ground-truth evidence gaps (designated G-candidates). 

This audit analyzes all 5 questions against three independent corpus tiers:
1. **Current Gold Chunks** (`data/corpus/chunks.json`)
2. **Other Corpus Chunks** (subsequent chunks of the same document)
3. **Document Metadata** (`data/corpus/papers.json`)
4. **Knowledge Graph** (Neo4j active database)

### Taxonomy
- **G1 (Gold Incomplete)**: The corpus genuinely lacks authoritative evidence to answer the question. The question cannot be answered from ingested materials.
- **G2 (Source Mismatch)**: Authoritative evidence exists within the ingested document corpus/metadata, but the benchmark annotation points at the wrong, incomplete, or truncated evidence source (e.g., chunk 000 without chunk 001, or text chunk omitting paper author metadata).

### Audit Verdict
**All 5 candidates are classified as G2 (Source Mismatch). 0 candidates are classified as G1.**
The enterprise corpus contains 100% of the facts required to answer every question authoritatively; the benchmark `gold_chunk_ids` failed because it only permitted single/partial text chunk pointers and excluded metadata fields and multi-chunk abstracts.

---

## Comprehensive Evidence Audit Table

| question_id | required_fact_id | required_fact | current_gold_chunk_ids | fact_in_current_gold | fact_in_other_chunk | fact_in_doc_meta | fact_in_neo4j | authoritative_source | classification | proposed_evidence_ids | verification_method |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `q_1hop_01` | `q1_f1` | Chuanyue Yu is an author | `chunk_arxiv_2507_23581v2_000` | ❌ No | ❌ No | ✅ Yes | ❌ No | `papers.json:arxiv_2507.23581v2` | **G2** | `meta_arxiv_2507_23581v2_authors` | Keyed lookup in `papers.json` |
| `q_1hop_01` | `q1_f2` | Kuo Zhao is an author | `chunk_arxiv_2507_23581v2_000` | ❌ No | ❌ No | ✅ Yes | ❌ No | `papers.json:arxiv_2507.23581v2` | **G2** | `meta_arxiv_2507_23581v2_authors` | Keyed lookup in `papers.json` |
| `q_1hop_01` | `q1_f3` | Heng Chang is an author | `chunk_arxiv_2507_23581v2_000` | ❌ No | ❌ No | ✅ Yes | ❌ No | `papers.json:arxiv_2507.23581v2` | **G2** | `meta_arxiv_2507_23581v2_authors` | Keyed lookup in `papers.json` |
| `q_1hop_04` | `q4_f1` | Sheroz Shaikh is the author | `chunk_arxiv_2606_21553v1_000` | ❌ No | ❌ No | ✅ Yes | ❌ No | `papers.json:arxiv_2606.21553v1` | **G2** | `meta_arxiv_2606_21553v1_authors` | Keyed lookup in `papers.json` |
| `q_1hop_04` | `q4_f2` | Evaluates a local 7B model | `chunk_arxiv_2606_21553v1_000` | ✅ Yes | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2606_21553v1_000` | **G2** | `chunk_arxiv_2606_21553v1_000` | Substring match in chunk 000 |
| `q_2hop_02` | `q2hop2_f1` | Fact retrieval and complex reasoning | `chunk_arxiv_2506_05690v3_000` | ❌ No | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2506_05690v3_001` | **G2** | `chunk_arxiv_2506_05690v3_001` | Verbatim substring in chunk 001 |
| `q_2hop_02` | `q2hop2_f2` | Contextual summarization and creative generation | `chunk_arxiv_2506_05690v3_000` | ❌ No | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2506_05690v3_001` | **G2** | `chunk_arxiv_2506_05690v3_001` | Verbatim substring in chunk 001 |
| `q_2hop_05` | `q2hop5_f1` | Verse-level retrieval corpus | `chunk_arxiv_2601_07528v2_000` | ❌ No | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2601_07528v2_001` | **G2** | `chunk_arxiv_2601_07528v2_001` | Verbatim substring in chunk 001 |
| `q_2hop_05` | `q2hop5_f2` | Approximately 6,000 verses | `chunk_arxiv_2601_07528v2_000` | ❌ No | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2601_07528v2_001` | **G2** | `chunk_arxiv_2601_07528v2_001` | Verbatim substring in chunk 001 |
| `q_agg_04` | `qagg4_f1` | HeRo optimizes adaptive orchestration on mobile SoCs | `chunk_arxiv_2603_01661v2_000`, `chunk_arxiv_2508_20324v4_000` | ✅ Yes | ✅ Yes | ❌ No | ❌ No | `chunk_arxiv_2603_01661v2_000` | **G2** | `chunk_arxiv_2603_01661v2_000` | Substring match in chunk 000 |
| `q_agg_04` | `qagg4_f2` | Kotoge et al. distill agentic search into compact 0.5-1B models | `chunk_arxiv_2603_01661v2_000`, `chunk_arxiv_2508_20324v4_000` | ❌ No | ❌ No | ✅ Yes | ❌ No | `papers.json:arxiv_2508.20324v4` + `chunk_arxiv_2508_20324v4_000` | **G2** | `chunk_arxiv_2508_20324v4_000`, `meta_arxiv_2508_20324v4_authors` | Chunk text + author metadata lookup |

---

## Detailed Per-Candidate Analysis

### 1. `q_1hop_01`
- **Question**: "Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning?"
- **Current Gold Chunk**: `chunk_arxiv_2507_23581v2_000`
- **Current Gold Chunk Text**:
  > "Graph Retrieval-Augmented Generation (GraphRAG) has shown great effectiveness in enhancing the reasoning abilities of LLMs by leveraging graph structures for knowledge representation and modeling complex real-world relationships. However, existing GraphRAG methods still face significant bottlenecks when handling complex problems that require multi-hop reasoning, as their query and retrieval phases are largely based on pre-defined heuristics and do not fully utilize the reasoning potentials of LLMs. To address this problem, we propose GraphRAG-R1, an adaptive GraphRAG framework by training LLMs with process-constrained outcome-based reinforcement learning (RL) to enhance the multi-hop reasoning ability."
- **Failure Cause**: The text chunk contains the abstract text body, but paper author names are stored in arXiv document header metadata, not in the body chunk text. As a result, Oracle was handed a chunk without the author names and correctly refused.
- **Authoritative Source**: `data/corpus/papers.json` under key `arxiv_2507.23581v2`:
  ```json
  "authors": [
    "Chuanyue Yu", "Kuo Zhao", "Yuhan Li", "Heng Chang", 
    "Mingjian Feng", "Xiangzhe Jiang", "Yufei Sun", "Jia Li", 
    "Yuzhi Zhang", "Jianxin Li", "Ziwei Zhang"
  ]
  ```
- **Classification**: **G2** (Source mismatch: metadata field vs. text chunk).
- **Proposed Evidence**:
  ```json
  [
    {
      "type": "metadata",
      "id": "meta_arxiv_2507_23581v2_authors",
      "document_id": "arxiv_2507.23581v2",
      "field": "authors"
    }
  ]
  ```

---

### 2. `q_1hop_04`
- **Question**: "Who authored the component ablation study 'Dissecting Agentic RAG' for multi-hop QA?"
- **Current Gold Chunk**: `chunk_arxiv_2606_21553v1_000`
- **Current Gold Chunk Text**:
  > "Agentic retrieval-augmented generation (RAG) systems combine iterative reasoning loops, query decomposition, and adaptive retrieval to tackle multi-hop question answering. However, the contribution of each component remains poorly understood, particularly under resource-constrained settings using only local language models... To test whether it does, we run a controlled ablation study of a full agentic RAG pipeline evaluated on 5,000 questions from the HotpotQA distractor development set using a local 7B parameter model (Qwen2.5-7B-Instruct)."
- **Failure Cause**: `q4_f2` ("Evaluates a local 7B model") was present, but `q4_f1` ("Sheroz Shaikh is the author") was missing because the author was only in metadata. Oracle correctly stated that the paper text did not identify the author.
- **Authoritative Source**: `data/corpus/papers.json` under key `arxiv_2606.21553v1`:
  ```json
  "authors": ["Sheroz Shaikh"]
  ```
- **Classification**: **G2** (Source mismatch: hybrid document metadata + text chunk).
- **Proposed Evidence**:
  ```json
  [
    {
      "type": "metadata",
      "id": "meta_arxiv_2606_21553v1_authors",
      "document_id": "arxiv_2606.21553v1",
      "field": "authors"
    },
    {
      "type": "chunk",
      "id": "chunk_arxiv_2606_21553v1_000",
      "document_id": "arxiv_2606.21553v1",
      "section_path": "Abstract"
    }
  ]
  ```

---

### 3. `q_2hop_02`
- **Question**: "What four task categories are covered by the GraphRAG-Bench evaluation suite introduced by Zhishang Xiang et al.?"
- **Current Gold Chunk**: `chunk_arxiv_2506_05690v3_000`
- **Current Gold Chunk Text**:
  > "Graph retrieval-augmented generation (GraphRAG) has emerged as a powerful paradigm for enhancing large language models (LLMs) with external knowledge... To address this, we propose GraphRAG-Bench, a comprehensive benchmark designed to evaluate GraphRAG models onboth hierarchical knowledge retrieval and deep contextual reasoning."
- **Failure Cause**: The abstract was chunked across two chunks. Chunk `000` introduces GraphRAG-Bench. Chunk `001` enumerates the four task categories. Gold annotation only pointed to chunk `000`.
- **Authoritative Source**: `chunk_arxiv_2506_05690v3_001`:
  > "GraphRAG-Bench features a comprehensive dataset with tasks of increasing difficulty, covering fact retrieval, complex reasoning, contextual summarization, and creative generation, and a systematic evaluation across the entire pipeline..."
- **Classification**: **G2** (Source mismatch: missing chunk continuation).
- **Proposed Evidence**:
  ```json
  [
    {
      "type": "chunk",
      "id": "chunk_arxiv_2506_05690v3_000",
      "document_id": "arxiv_2506.05690v3",
      "section_path": "Abstract"
    },
    {
      "type": "chunk",
      "id": "chunk_arxiv_2506_05690v3_001",
      "document_id": "arxiv_2506.05690v3",
      "section_path": "Abstract"
    }
  ]
  ```

---

### 4. `q_2hop_05`
- **Question**: "What retrieval corpus granularity does the IslamicFaithQA framework develop for agentic Quran-grounding?"
- **Current Gold Chunk**: `chunk_arxiv_2601_07528v2_000`
- **Current Gold Chunk Text**:
  > "Large Language Models (LLMs) are increasingly used for Islamic question answering, where ungrounded responses may carry serious religious consequences... We provide: (i) 15K Arabic text-grounded SFT reasoning pairs,"
- **Failure Cause**: Chunk `000` truncates right after `(i)`. Chunk `001` contains `(iii) a verse-level Qur'an retrieval corpus of ~6k atomic verses (ayat)`. The benchmark only listed chunk `000`.
- **Authoritative Source**: `chunk_arxiv_2601_07528v2_001`:
  > "and (iii) a verse-level Qur'an retrieval corpus of ~6k atomic verses (ayat). Building on these resources, we develop an agentic Quran-grounding framework (agentic RAG) that uses structured tool calls for iterative evidence seeking and answer revision."
- **Classification**: **G2** (Source mismatch: missing chunk continuation).
- **Proposed Evidence**:
  ```json
  [
    {
      "type": "chunk",
      "id": "chunk_arxiv_2601_07528v2_000",
      "document_id": "arxiv_2601.07528v2",
      "section_path": "Abstract"
    },
    {
      "type": "chunk",
      "id": "chunk_arxiv_2601_07528v2_001",
      "document_id": "arxiv_2601.07528v2",
      "section_path": "Abstract"
    }
  ]
  ```

---

### 5. `q_agg_04`
- **Question**: "Compare the efficiency strategies of HeRo and Kotoge et al. for running Agentic RAG on resource-constrained hardware."
- **Current Gold Chunks**: `chunk_arxiv_2603_01661v2_000`, `chunk_arxiv_2508_20324v4_000`
- **Current Gold Chunk Text**:
  - `chunk_arxiv_2603_01661v2_000` describes HeRo's mobile SoC adaptive orchestration.
  - `chunk_arxiv_2508_20324v4_000` describes DGPO compact 0.5-1B model reinforcement learning.
- **Failure Cause**: While both technique abstracts are present, chunk `chunk_arxiv_2508_20324v4_000` does not state the author names ("Kotoge et al."). The Oracle LLM stated that while HeRo was described, no paper by "Kotoge et al." was present in the provided context, triggering an evidence refusal for that sub-fact.
- **Authoritative Source**: Document metadata for `arxiv_2508.20324v4` resolves authors `["Rikuto Kotoge", "Mai Nishimura", "Jiaxin Ma"]`.
- **Classification**: **G2** (Source mismatch: multi-chunk + document metadata grounding).
- **Proposed Evidence**:
  ```json
  [
    {
      "type": "chunk",
      "id": "chunk_arxiv_2603_01661v2_000",
      "document_id": "arxiv_2603.01661v2",
      "section_path": "Abstract"
    },
    {
      "type": "chunk",
      "id": "chunk_arxiv_2508_20324v4_000",
      "document_id": "arxiv_2508.20324v4",
      "section_path": "Abstract"
    },
    {
      "type": "metadata",
      "id": "meta_arxiv_2508_20324v4_authors",
      "document_id": "arxiv_2508.20324v4",
      "field": "authors"
    }
  ]
  ```

---

## Multi-Source Evidence Schema Recommendation

To avoid forcing graph metadata or document headers into arbitrary text-chunk IDs, the gold dataset schema should cleanly support typed evidence records:

```json
{
  "question_id": "q_1hop_04",
  "gold_evidence": [
    {
      "type": "metadata",
      "id": "meta_arxiv_2606_21553v1_authors",
      "document_id": "arxiv_2606.21553v1",
      "field": "authors"
    },
    {
      "type": "chunk",
      "id": "chunk_arxiv_2606_21553v1_000",
      "document_id": "arxiv_2606.21553v1",
      "section_path": "Abstract"
    }
  ]
}
```

### Retrieval Evaluation Separation
1. **Text Chunk Recall**: Computed strictly over evidence items where `type == "chunk"`.
2. **Entity / Graph / Metadata Recall**: Computed over evidence items where `type in ["metadata", "graph_fact"]`.
3. **Oracle Generation Assembly**: Assembles text chunks alongside formatted document metadata headers (`Title: ... | Authors: ...`), guaranteeing the generator receives complete grounding without synthetic hallucination or metric pollution.
