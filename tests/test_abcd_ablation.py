# -*- coding: utf-8 -*-
import pytest
from src.eval.models_v2 import BenchmarkQuestionV2, QuestionAuditRecord, RequiredFact
from scripts.run_abcd_ablation import classify_hybrid_failure, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("hello world") == 3
    assert estimate_tokens("") == 0


def test_classify_hybrid_failure_type_a():
    q = BenchmarkQuestionV2(
        id="q_test_1",
        hop_type="1-hop",
        question="What is X?",
        reference_answer="X is Y.",
        required_facts=[RequiredFact(id="f1", fact="X is Y", weight=1.0)],
        gold_chunk_ids=["chunk_001"],
        answerable=True,
    )
    rec_v = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=0.0,
        retrieval_recall=0.0,
        generated_answer="Insufficient evidence.",
        model_name="vector",
    )
    rec_h = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=0.0,
        retrieval_recall=0.0,
        generated_answer="Insufficient evidence.",
        model_name="hybrid",
        graph_facts=[],
    )
    rec_o = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=1.0,
        retrieval_recall=1.0,
        generated_answer="X is Y.",
        model_name="oracle",
    )
    cat, reason = classify_hybrid_failure(q, rec_v, rec_h, rec_o, {"context_tokens_estimate": 150})
    assert cat == "A"


def test_classify_hybrid_failure_type_d():
    q = BenchmarkQuestionV2(
        id="q_test_2",
        hop_type="2-hop",
        question="What is Z?",
        reference_answer="Z is W.",
        required_facts=[RequiredFact(id="f1", fact="Z is W", weight=1.0)],
        gold_chunk_ids=["chunk_002"],
        answerable=True,
    )
    rec_v = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=0.0,
        retrieval_recall=0.0,
        generated_answer="Insufficient evidence.",
        model_name="vector",
    )
    rec_h = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=0.0,
        retrieval_recall=1.0,
        retrieval_precision=0.05,
        generated_answer="Confused answer.",
        model_name="hybrid",
    )
    rec_o = QuestionAuditRecord(
        question_id=q.id,
        hop_type=q.hop_type,
        answerable=True,
        fact_score=1.0,
        retrieval_recall=1.0,
        generated_answer="Z is W.",
        model_name="oracle",
    )
    cat, reason = classify_hybrid_failure(q, rec_v, rec_h, rec_o, {"context_tokens_estimate": 1200})
    assert cat == "D"
