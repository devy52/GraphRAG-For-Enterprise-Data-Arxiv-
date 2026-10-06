# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
Evaluation V2 Data Contracts and Models.

Architecture Role:
    Defines the authoritative fact-level ground-truth models and score records
    for the Evaluation V2 framework. Decouples evaluation into five independent
    layers (Retrieval, Factual Correctness, Context Groundedness, Answerability/
    Abstention, and Efficiency).

    The models deliberately keep factual correctness, groundedness, retrieval
    correctness, abstention, and lexical proxies separate. None means a
    metric was not evaluable; it is never silently converted to a perfect score.

Inputs:
    - Gold benchmark specifications with structured required facts, aliases, and weights.

Outputs:
    - Typed models for benchmark questions, per-question audit records, and aggregate evaluation results.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EvalHopTypeV2(str, Enum):
    ONE_HOP = "1-hop"
    TWO_HOP = "2-hop"
    THREE_HOP = "3-hop"
    AGGREGATION = "aggregation"
    OUT_OF_SCOPE = "out-of-scope"


class RequiredFact(BaseModel):
    """Atomic fact required for a substantive answer."""

    id: str
    fact: str
    weight: float = 1.0
    aliases: List[str] = Field(default_factory=list)

    @field_validator("weight")
    @classmethod
    def positive_weight(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Required fact weight must be > 0")
        return value


class OptionalFact(BaseModel):
    """Supplementary fact; currently informational and not part of correctness."""

    id: str
    fact: str
    weight: float = 0.5
    aliases: List[str] = Field(default_factory=list)

    @field_validator("weight")
    @classmethod
    def positive_weight(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Optional fact weight must be > 0")
        return value


class GoldEvidenceType(str, Enum):
    CHUNK = "chunk"
    METADATA = "metadata"
    GRAPH_FACT = "graph_fact"


class GoldEvidenceItem(BaseModel):
    """Authoritative evidence item supporting one or more required facts."""

    type: GoldEvidenceType
    id: str
    supports: List[str] = Field(default_factory=list)
    document_id: Optional[str] = None
    field: Optional[str] = None
    text: Optional[str] = None


class BenchmarkQuestionV2(BaseModel):
    """Authoritative benchmark record with structured ground truth."""

    id: str
    question: str
    reference_answer: str
    required_facts: List[RequiredFact] = Field(default_factory=list)
    optional_facts: List[OptionalFact] = Field(default_factory=list)
    answerable: bool = True
    hop_type: EvalHopTypeV2
    target_entities: List[str] = Field(default_factory=list)
    gold_chunk_ids: List[str] = Field(default_factory=list)
    gold_evidence: List[GoldEvidenceItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ground_truth(self) -> "BenchmarkQuestionV2":
        if self.answerable and not self.required_facts:
            raise ValueError(f"Answerable question {self.id} must define required_facts")
        if self.answerable and self.hop_type == EvalHopTypeV2.OUT_OF_SCOPE:
            raise ValueError(f"Answerable question {self.id} cannot be out-of-scope")
        if not self.answerable and self.hop_type != EvalHopTypeV2.OUT_OF_SCOPE:
            raise ValueError(f"Unanswerable question {self.id} must use out-of-scope hop_type")

        # Sync gold_chunk_ids and gold_evidence
        if self.gold_evidence and not self.gold_chunk_ids:
            self.gold_chunk_ids = [
                item.id for item in self.gold_evidence if item.type == GoldEvidenceType.CHUNK
            ]
        elif self.gold_chunk_ids and not self.gold_evidence:
            all_fact_ids = [f.id for f in self.required_facts]
            self.gold_evidence = [
                GoldEvidenceItem(
                    type=GoldEvidenceType.CHUNK,
                    id=cid,
                    supports=all_fact_ids,
                )
                for cid in self.gold_chunk_ids
            ]
        return self


class QuestionAuditRecord(BaseModel):
    """One fully auditable benchmark observation."""

    question_id: str
    hop_type: str
    answerable: bool
    generated_answer: str

    # Layer A: Unified / Effective Retrieval Correctness.
    retrieval_evaluable: bool = False
    retrieval_precision: Optional[float] = None
    retrieval_recall: Optional[float] = None
    retrieval_mrr: Optional[float] = None
    retrieved_chunk_ids: List[str] = Field(default_factory=list)
    retrieved_chunk_texts: List[str] = Field(default_factory=list)
    available_evidence_ids: List[str] = Field(default_factory=list)

    # Layer A-1: Separated Vector Store Retrieval Metrics
    vector_retrieval_evaluable: bool = False
    vector_retrieval_precision: Optional[float] = None
    vector_retrieval_recall: Optional[float] = None
    vector_retrieval_mrr: Optional[float] = None
    substantive_chunk_recall: Optional[float] = None

    # Layer A-2: Separated Graph Topology Evidence Retrieval Metrics
    graph_retrieval_evaluable: bool = False
    graph_retrieval_precision: Optional[float] = None
    graph_retrieval_recall: Optional[float] = None
    graph_retrieval_mrr: Optional[float] = None
    graph_evidence_ids: List[str] = Field(default_factory=list)
    graph_provenance_chunk_ids: List[str] = Field(default_factory=list)
    graph_fact_recall: Optional[float] = None
    graph_facts: List[str] = Field(default_factory=list)
    complete_evidence_ledger: List[str] = Field(default_factory=list)

    # Layer A-3: Separated Document Metadata Evidence Retrieval Metrics
    metadata_retrieval_evaluable: bool = False
    metadata_retrieval_precision: Optional[float] = None
    metadata_retrieval_recall: Optional[float] = None
    metadata_recall: Optional[float] = None
    metadata_evidence_ids: List[str] = Field(default_factory=list)
    unified_evidence_recall: Optional[float] = None

    # Layer B: Fact Coverage (Evaluated via explicit atomic fact specifications).
    # None means factual correctness is not applicable, e.g. an intentionally unanswerable question.
    fact_evaluable: bool = False
    fact_score: Optional[float] = None
    facts_correct: int = 0
    facts_missing: int = 0
    facts_incorrect: int = 0
    facts_total: int = 0
    fact_coverage: Optional[float] = None
    satisfied_fact_ids: List[str] = Field(default_factory=list)
    missing_fact_ids: List[str] = Field(default_factory=list)
    incorrect_fact_ids: List[str] = Field(default_factory=list)
    fact_verdicts: List[Dict[str, Any]] = Field(default_factory=list)
    fact_evaluation_method: str = "structured_atomic_fact_proxy"

    # Layer C: Context Groundedness.
    context_groundedness: float = 0.0
    unsupported_claim_rate: float = 0.0
    groundedness_method: str = "lexical_overlap_heuristic"
    judge_model: str = ""

    # Layer D: Answerability / Abstention.
    # ``abstention_correct`` is retained for compatibility and now means ONLY
    # a correctly classified abstention.  ``did_not_abstain`` describes the
    # opposite case explicitly.
    abstention_correct: bool = False
    did_not_abstain: bool = False
    answerable_correct: bool = False
    answerable_incorrect: bool = False
    correctly_abstained: bool = False
    incorrectly_abstained: bool = False

    # Layer E: Efficiency.
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Lexical proxies, explicitly labeled as proxy heuristics (not semantic/factual correctness).
    reference_text_token_f1: float = 0.0
    lexical_fact_proxy_token_f1: float = 0.0
    lexical_chunk_overlap_utilization: float = 0.0
    invalid_citation_reference_rate: float = 0.0

    # Metadata and provenance.
    model_name: str = ""
    timestamp: str = ""
    citations: List[str] = Field(default_factory=list)
    error_state: Optional[str] = None
    dataset_sha256: str = ""
