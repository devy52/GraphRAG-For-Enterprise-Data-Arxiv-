"""
Evaluation Dataset and Stratified Benchmark Question Catalog.

Architecture Role:
    Part of Phase 8 (Benchmarking & Evaluation Suite). Defines the structured schemas and canonical
    evaluation dataset used to compare Hybrid GraphRAG against the Plain Vector RAG baseline.
    The benchmark is stratified across query complexity: single-hop (1-hop), relational (2-hop),
    multi-hop graph traversals (3-hop), corpus-level aggregations, and out-of-scope refusals.

Inputs:
    - Curated scientific research questions in the RAG/retrieval domain.

Outputs:
    - Typed `BenchmarkDataset` and `EvalQuestion` models with ground-truth keywords,
      target entities, and expected refusal flags.

Design Decisions:
    - Stratified Evaluation: Isolates performance differences by hop complexity, directly exposing
      the inflection point where vector search recall degrades and graph traversal succeeds.
    - Deterministic Keyword Scoring: Evaluates accuracy and grounding by verifying whether
      synthesized answers contain expected factual keyword entities and valid source citations.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class EvalHopType(str, Enum):
    """
    Categorization of question structural complexity.
    """
    ONE_HOP = "1-hop"                # Direct factual lookup (e.g. author of paper, dataset used)
    TWO_HOP = "2-hop"                # 1-degree relational jump (e.g. co-authorship, method ancestry)
    THREE_HOP = "3-hop"              # Multi-hop graph traversal (e.g. citation chains A->B->C, transitive lineage)
    AGGREGATION = "aggregation"      # Corpus-wide summary or comparison across multiple methods/datasets
    OUT_OF_SCOPE = "out-of-scope"    # Irrelevant or unanswerable queries where system must refuse/state lack of evidence


class EvalQuestion(BaseModel):
    """
    A single benchmark question with evaluation ground-truth criteria.
    """
    id: str = Field(..., description="Unique question identifier (e.g. q_1hop_01)")
    question: str = Field(..., description="Natural language query string")
    hop_type: EvalHopType = Field(..., description="Structural complexity category")
    target_entities: List[str] = Field(
        default_factory=list,
        description="Key canonical entities involved in the query",
    )
    expected_answer_keywords: List[str] = Field(
        default_factory=list,
        description="Factual terms expected in an accurate, grounded answer",
    )
    should_refuse: bool = Field(
        default=False,
        description="True if the question is out of scope and the system should state lack of evidence",
    )


class BenchmarkDataset(BaseModel):
    """
    Container for the complete stratified evaluation set.
    """
    name: str = Field(default="RAG-Enterprise-Benchmark-v1", description="Dataset identifier")
    description: str = Field(
        default="Stratified evaluation set for scientific GraphRAG benchmarking",
        description="Description of the benchmark scope",
    )
    questions: List[EvalQuestion] = Field(default_factory=list, description="List of benchmark questions")

    def filter_by_hop(self, hop_type: EvalHopType) -> List[EvalQuestion]:
        """Returns questions matching a specific hop complexity."""
        return [q for q in self.questions if q.hop_type == hop_type]


def get_canonical_evaluation_dataset() -> BenchmarkDataset:
    """
    Constructs the canonical 50-question stratified benchmark dataset for enterprise GraphRAG evaluation.
    """
    questions: List[EvalQuestion] = [
        # ======================================================================
        # 1-Hop Questions (Direct Lookup) - 10 Questions
        # ======================================================================
        EvalQuestion(
            id="q_1hop_01",
            question="Who are the primary authors of the Dense Passage Retrieval paper?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval", "Patrick Lewis"],
            expected_answer_keywords=["Vladimir Karpukhin", "Barlas Oguz", "Patrick Lewis"],
        ),
        EvalQuestion(
            id="q_1hop_02",
            question="What primary model architecture is proposed in the RAG paper?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Retrieval-Augmented Generation"],
            expected_answer_keywords=["RAG-Sequence", "RAG-Token", "generator", "retriever"],
        ),
        EvalQuestion(
            id="q_1hop_03",
            question="What dataset was used to evaluate Natural Questions in DPR?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Natural Questions", "Dense Passage Retrieval"],
            expected_answer_keywords=["Natural Questions", "NQ", "Wikipedia"],
        ),
        EvalQuestion(
            id="q_1hop_04",
            question="Which sparse retrieval baseline did DPR compare against?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval", "BM25"],
            expected_answer_keywords=["BM25", "Lucene"],
        ),
        EvalQuestion(
            id="q_1hop_05",
            question="Who authored the ColBERT late-interaction retrieval paper?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["ColBERT"],
            expected_answer_keywords=["Omar Khattab", "Matei Zaharia"],
        ),
        EvalQuestion(
            id="q_1hop_06",
            question="What loss function does DPR use for training its dual encoders?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["negative log-likelihood", "contrastive", "in-batch negatives"],
        ),
        EvalQuestion(
            id="q_1hop_07",
            question="What encoder backbone was used in the original DPR experiments?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval", "BERT"],
            expected_answer_keywords=["BERT", "BERT-base"],
        ),
        EvalQuestion(
            id="q_1hop_08",
            question="What generator model is paired with the DPR retriever in the RAG paper?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Retrieval-Augmented Generation", "BART"],
            expected_answer_keywords=["BART", "BART-large"],
        ),
        EvalQuestion(
            id="q_1hop_09",
            question="What index type does DPR employ for fast MIPS passage search?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval", "FAISS"],
            expected_answer_keywords=["FAISS", "HNSW", "Flat"],
        ),
        EvalQuestion(
            id="q_1hop_10",
            question="What is the dimension of the embedding vectors produced by DPR?",
            hop_type=EvalHopType.ONE_HOP,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["768", "dimension"],
        ),

        # ======================================================================
        # 2-Hop Questions (Relational Links) - 10 Questions
        # ======================================================================
        EvalQuestion(
            id="q_2hop_01",
            question="Which researchers co-authored papers with Patrick Lewis on retrieval-augmented models?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Patrick Lewis"],
            expected_answer_keywords=["Ethan Perez", "Aleksandra Piktus", "Sebastian Riedel"],
        ),
        EvalQuestion(
            id="q_2hop_02",
            question="What retrieval methods extend the dual-encoder architecture introduced by DPR?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["ANCE", "RocketQA", "ColBERT"],
        ),
        EvalQuestion(
            id="q_2hop_03",
            question="What datasets are shared between the evaluation of DPR and ColBERT?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Dense Passage Retrieval", "ColBERT"],
            expected_answer_keywords=["MS MARCO", "Natural Questions", "TriviaQA"],
        ),
        EvalQuestion(
            id="q_2hop_04",
            question="Which papers cite both the original Transformer paper and the DPR paper?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Attention Is All You Need", "Dense Passage Retrieval"],
            expected_answer_keywords=["Retrieval-Augmented Generation", "FiD", "Fusion-in-Decoder"],
        ),
        EvalQuestion(
            id="q_2hop_05",
            question="Which institutions published research co-authored by Omar Khattab and Matei Zaharia?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Omar Khattab", "Matei Zaharia"],
            expected_answer_keywords=["Stanford", "Stanford University"],
        ),
        EvalQuestion(
            id="q_2hop_06",
            question="What generative architectures were evaluated on TriviaQA using dense retrieval?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["TriviaQA", "Dense Passage Retrieval"],
            expected_answer_keywords=["BART", "T5", "RAG"],
        ),
        EvalQuestion(
            id="q_2hop_07",
            question="What methods use hard negative mining techniques derived from DPR's BM25 negatives?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Dense Passage Retrieval", "BM25"],
            expected_answer_keywords=["ANCE", "RocketQA", "hard negatives"],
        ),
        EvalQuestion(
            id="q_2hop_08",
            question="Who are the common collaborators between the authors of RAG and the authors of FiD?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Retrieval-Augmented Generation", "Fusion-in-Decoder"],
            expected_answer_keywords=["Gautier Izacard", "Edouard Grave", "Sebastian Riedel"],
        ),
        EvalQuestion(
            id="q_2hop_09",
            question="What benchmarks evaluate multi-hop reasoning over documents retrieved by DPR?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["Dense Passage Retrieval", "HotpotQA"],
            expected_answer_keywords=["HotpotQA", "multi-hop"],
        ),
        EvalQuestion(
            id="q_2hop_10",
            question="What methods adapt late-interaction token scoring to dense passage representations?",
            hop_type=EvalHopType.TWO_HOP,
            target_entities=["ColBERT", "Dense Passage Retrieval"],
            expected_answer_keywords=["ColBERTv2", "PLAID", "late interaction"],
        ),

        # ======================================================================
        # 3-Hop Questions (Multi-Hop Lineage & Chains) - 10 Questions
        # ======================================================================
        EvalQuestion(
            id="q_3hop_01",
            question="Find the citation chain from BM25 through DPR to Fusion-in-Decoder and compare their methodologies.",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["BM25", "Dense Passage Retrieval", "Fusion-in-Decoder"],
            expected_answer_keywords=["sparse", "dense dual-encoder", "cross-attention", "FiD"],
        ),
        EvalQuestion(
            id="q_3hop_02",
            question="Which authors have published papers citing models that extend the contrastive retrieval framework of DPR?",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["Karpukhin", "Xiong", "Zhan"],
        ),
        EvalQuestion(
            id="q_3hop_03",
            question="Trace how the passage chunking strategy used in DPR influenced the retrieval stages of RAG and FiD.",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["Dense Passage Retrieval", "Retrieval-Augmented Generation", "Fusion-in-Decoder"],
            expected_answer_keywords=["100 words", "passage", "disjoint chunks", "top-k"],
        ),
        EvalQuestion(
            id="q_3hop_04",
            question="Which methods that cite DPR evaluate on HotpotQA and also utilize cross-encoder rerankers?",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["Dense Passage Retrieval", "HotpotQA"],
            expected_answer_keywords=["reranker", "cross-encoder", "HotpotQA"],
        ),
        EvalQuestion(
            id="q_3hop_05",
            question="Identify the lineage connecting BERT embeddings to dense retrieval and subsequently to late-interaction index compression.",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["BERT", "Dense Passage Retrieval", "ColBERT"],
            expected_answer_keywords=["BERT", "bi-encoder", "MaxSim", "ColBERTv2", "residual compression"],
        ),
        EvalQuestion(
            id="q_3hop_06",
            question="Find the co-authorship path connecting Matei Zaharia to Sebastian Riedel through intermediate collaborators.",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["Matei Zaharia", "Sebastian Riedel"],
            expected_answer_keywords=["Omar Khattab", "Patrick Lewis", "collaborator"],
        ),
        EvalQuestion(
            id="q_3hop_07",
            question="What sequence of papers established the progression from exact keyword matching to dense bi-encoders and parametric generator fusion?",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["BM25", "Dense Passage Retrieval", "Retrieval-Augmented Generation"],
            expected_answer_keywords=["BM25", "DPR", "RAG", "BART", "parametric"],
        ),
        EvalQuestion(
            id="q_3hop_08",
            question="Which models cite ANCE and evaluate on datasets that were originally used to benchmark DPR?",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["ANCE", "Dense Passage Retrieval", "Natural Questions"],
            expected_answer_keywords=["ANCE", "Natural Questions", "TriviaQA", "RocketQA"],
        ),
        EvalQuestion(
            id="q_3hop_09",
            question="Trace the evolution of negative sampling strategies from in-batch negatives to iteratively mined hard negatives across RAG literature.",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["Dense Passage Retrieval", "ANCE"],
            expected_answer_keywords=["in-batch", "BM25 negatives", "asynchronous", "ANCE"],
        ),
        EvalQuestion(
            id="q_3hop_10",
            question="What methods connecting late-interaction retrieval and multi-vector representations were evaluated on MS MARCO?",
            hop_type=EvalHopType.THREE_HOP,
            target_entities=["ColBERT", "MS MARCO"],
            expected_answer_keywords=["ColBERT", "ColBERTv2", "MS MARCO", "passage ranking"],
        ),

        # ======================================================================
        # Aggregation / Comparative Questions - 10 Questions
        # ======================================================================
        EvalQuestion(
            id="q_agg_01",
            question="Compare the top-20 retrieval accuracy of DPR, BM25, and ColBERT across open-domain benchmarks.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Dense Passage Retrieval", "BM25", "ColBERT"],
            expected_answer_keywords=["accuracy", "top-20", "outperforms", "NQ"],
        ),
        EvalQuestion(
            id="q_agg_02",
            question="List all open-domain QA evaluation datasets mentioned across the papers in the corpus.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Natural Questions", "TriviaQA", "HotpotQA", "WebQuestions"],
            expected_answer_keywords=["Natural Questions", "TriviaQA", "HotpotQA", "CuratedTREC"],
        ),
        EvalQuestion(
            id="q_agg_03",
            question="Summarize the different passage retrieval indexing techniques employed across all methods in the corpus.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["FAISS", "HNSW", "Inverted Index"],
            expected_answer_keywords=["FAISS", "HNSW", "inverted index", "quantization"],
        ),
        EvalQuestion(
            id="q_agg_04",
            question="Compare the parameter counts and model backbones used by RAG and Fusion-in-Decoder.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Retrieval-Augmented Generation", "Fusion-in-Decoder"],
            expected_answer_keywords=["BART", "T5", "parameters", "encoder-decoder"],
        ),
        EvalQuestion(
            id="q_agg_05",
            question="What are the recurring failure modes of dense retrieval identified across the literature?",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["out-of-domain", "entity names", "rare words", "generalization"],
        ),
        EvalQuestion(
            id="q_agg_06",
            question="List all primary researchers who have contributed to at least two different papers in the corpus.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Patrick Lewis", "Sebastian Riedel", "Matei Zaharia"],
            expected_answer_keywords=["Patrick Lewis", "Sebastian Riedel"],
        ),
        EvalQuestion(
            id="q_agg_07",
            question="Compare the computational latency trade-offs between dual-encoders and late-interaction architectures.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Dense Passage Retrieval", "ColBERT"],
            expected_answer_keywords=["MIPS", "dot product", "late interaction", "MaxSim", "latency"],
        ),
        EvalQuestion(
            id="q_agg_08",
            question="What chunk sizes and token lengths are predominantly used for passage segmentation in dense retrieval?",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Dense Passage Retrieval"],
            expected_answer_keywords=["100 words", "256 tokens", "passage", "overlap"],
        ),
        EvalQuestion(
            id="q_agg_09",
            question="Synthesize the evolutionary trajectory of retrieval augmentation from static index lookups to end-to-end trained models.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["BM25", "Dense Passage Retrieval", "Retrieval-Augmented Generation"],
            expected_answer_keywords=["evolution", "BM25", "differentiable", "end-to-end", "joint training"],
        ),
        EvalQuestion(
            id="q_agg_10",
            question="Provide a structured breakdown of retrieval metrics (MRR@10, Recall@20, EM) reported across the papers.",
            hop_type=EvalHopType.AGGREGATION,
            target_entities=["Natural Questions", "MS MARCO"],
            expected_answer_keywords=["MRR@10", "Recall@20", "Exact Match", "EM"],
        ),

        # ======================================================================
        # Out-of-Scope / Refusal Questions - 10 Questions
        # ======================================================================
        EvalQuestion(
            id="q_oos_01",
            question="What is the chemical mechanism of photosynthesis in C4 plants?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_02",
            question="How do black holes evaporate via Hawking radiation?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_03",
            question="What is the traditional recipe for French onion soup?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_04",
            question="What are the symptoms and diagnostic criteria for Type 2 diabetes?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_05",
            question="Who won the FIFA World Cup in 1998?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_06",
            question="Explain the general theory of relativity and spacetime curvature.",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_07",
            question="What are the best soil conditions for growing tomatoes in a greenhouse?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_08",
            question="How do internal combustion engines compare to electric motor drivetrains?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_09",
            question="What is the history of the Renaissance period in northern Italy?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
        EvalQuestion(
            id="q_oos_10",
            question="How is acoustic guitar soundboard bracing designed for tone projection?",
            hop_type=EvalHopType.OUT_OF_SCOPE,
            should_refuse=True,
            expected_answer_keywords=["no sufficient evidence", "lacks sufficient evidence"],
        ),
    ]

    return BenchmarkDataset(questions=questions)
