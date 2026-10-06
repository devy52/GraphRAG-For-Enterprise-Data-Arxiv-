# -*- coding: utf-8 -*-
"""
Comprehensive Regression Test Suite for Evaluation V2.

Verifies the 9 critical integrity properties specified in the Evaluation V2 refactor:
  1. Paraphrase acceptance (correct answers with varied wording score correctly).
  2. Unicode hyphen variants do not cause false negatives.
  3. Refusal to an answerable question is NOT counted as correct.
  4. Refusal to an unanswerable question CAN be correct (justified abstention).
  5. One matching keyword cannot make an otherwise wrong answer correct (no 'matches > 0').
  6. Question-ID-specific hardcoding cannot affect evaluation.
  7. Lexical chunk overlap cannot be interpreted as semantic utilization.
  8. Valid citation IDs are not classified as invalid.
  9. Invalid citation IDs are detected and reported.
"""

import pytest

from src.eval.evaluator_v2 import EvaluatorV2, compute_lexical_chunk_overlap, compute_token_f1
from src.eval.models_v2 import BenchmarkQuestionV2, EvalHopTypeV2, RequiredFact, OptionalFact


@pytest.fixture
def evaluator():
    return EvaluatorV2(enable_semantic_judge=False)


@pytest.fixture
def sample_answerable_question():
    return BenchmarkQuestionV2(
        id="q_1hop_01",
        question="Who are the primary authors of the Dense Passage Retrieval paper?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="The primary authors of the Dense Passage Retrieval (DPR) paper are Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, and Wen-tau Yih.",
        required_facts=[
            RequiredFact(id="q1_f1", fact="Vladimir Karpukhin is an author", weight=1.0, aliases=["vladimir karpukhin", "karpukhin"]),
            RequiredFact(id="q1_f2", fact="Barlas Oguz is an author", weight=1.0, aliases=["barlas oguz", "oguz"]),
            RequiredFact(id="q1_f3", fact="Patrick Lewis is an author", weight=1.0, aliases=["patrick lewis", "lewis"]),
        ],
        optional_facts=[
            OptionalFact(id="q1_o1", fact="Sewon Min or Danqi Chen", weight=0.5, aliases=["sewon min", "danqi chen"]),
        ],
        target_entities=["Dense Passage Retrieval", "Patrick Lewis"],
        gold_chunk_ids=["chunk_dpr_01", "chunk_dpr_02"],
    )


@pytest.fixture
def sample_unanswerable_question():
    return BenchmarkQuestionV2(
        id="q_oos_01",
        question="What is the chemical mechanism of photosynthesis in C4 plants?",
        hop_type=EvalHopTypeV2.OUT_OF_SCOPE,
        answerable=False,
        reference_answer="I cannot answer this question because the provided enterprise research corpus contains no evidence on plant biology or photosynthesis.",
        required_facts=[
            RequiredFact(id="qoos1_f1", fact="States lack of evidence in corpus / abstains", weight=1.0, aliases=["insufficient evidence", "cannot answer", "lacks sufficient evidence"]),
        ],
        target_entities=[],
        gold_chunk_ids=[],
    )


def test_paraphrase_acceptance(evaluator, sample_answerable_question):
    """1. A correct answer with paraphrased wording scores full fact credit."""
    paraphrased_answer = (
        "Dense Passage Retrieval was authored primarily by Patrick Lewis together with "
        "Vladimir Karpukhin and Barlas Oguz at Facebook AI Research."
    )
    audit = evaluator.evaluate_question(
        question=sample_answerable_question,
        generated_answer=paraphrased_answer,
        retrieved_chunk_ids=["chunk_dpr_01"],
        retrieved_chunk_texts=["DPR paper by Vladimir Karpukhin, Barlas Oguz, and Patrick Lewis."],
        citations=["chunk_dpr_01"],
    )

    assert audit.fact_score == 1.0
    assert audit.facts_correct == 3
    assert audit.facts_missing == 0
    assert audit.answerable_correct is True
    assert audit.answerable_incorrect is False


def test_unicode_hyphen_variants_no_false_negatives(evaluator):
    """2. Unicode hyphen variants (e.g. non-breaking hyphen) match equivalent ASCII required facts."""
    question = BenchmarkQuestionV2(
        id="q_1hop_06",
        question="What loss function does DPR use for training its dual encoders?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="DPR trains using negative log-likelihood (NLL) loss with in-batch negatives.",
        required_facts=[
            RequiredFact(id="q6_f1", fact="Negative log-likelihood loss", weight=1.0, aliases=["negative-log-likelihood", "nll"]),
            RequiredFact(id="q6_f2", fact="Uses in-batch negatives", weight=1.0, aliases=["in-batch negatives"]),
        ],
    )
    # Output generated with Unicode non-breaking hyphen (\u2011) and en-dash (\u2013)
    generated_with_unicode = (
        "The dual encoders are trained using negative\u2011log\u2011likelihood loss "
        "over in\u2013batch negatives."
    )
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=generated_with_unicode,
        retrieved_chunk_ids=["chunk_loss_01"],
        retrieved_chunk_texts=["Trained using negative log-likelihood with in-batch negatives."],
        citations=["chunk_loss_01"],
    )

    assert audit.fact_score == 1.0
    assert audit.facts_correct == 2
    assert audit.answerable_correct is True


def test_refusal_to_answerable_question_is_failure(evaluator, sample_answerable_question):
    """3. An answerable question that receives a refusal is NOT counted as factually correct."""
    refusal_answer = (
        "I cannot answer this question because there is insufficient evidence in the provided context."
    )
    audit = evaluator.evaluate_question(
        question=sample_answerable_question,
        generated_answer=refusal_answer,
        retrieved_chunk_ids=["chunk_dpr_01"],
        retrieved_chunk_texts=["Some text without author names."],
        citations=[],
    )

    assert audit.fact_score == 0.0
    assert audit.facts_correct == 0
    assert audit.facts_missing == 3
    assert audit.answerable_correct is False
    assert audit.answerable_incorrect is True
    assert audit.incorrectly_abstained is True
    assert audit.abstention_correct is False


def test_refusal_to_unanswerable_question_is_success(evaluator, sample_unanswerable_question):
    """4. A refusal to an unanswerable question CAN be correct (justified abstention)."""
    justified_refusal = (
        "I cannot answer this question because the corpus lacks sufficient evidence on photosynthesis."
    )
    audit = evaluator.evaluate_question(
        question=sample_unanswerable_question,
        generated_answer=justified_refusal,
        retrieved_chunk_ids=[],
        retrieved_chunk_texts=[],
        citations=[],
    )

    assert audit.fact_score is None
    assert audit.fact_evaluable is False
    assert audit.correctly_abstained is True
    assert audit.abstention_correct is True
    assert audit.answerable_incorrect is False
    assert audit.facts_incorrect == 0


def test_single_keyword_cannot_make_wrong_answer_correct(evaluator):
    """5. One matching keyword cannot make an otherwise incorrect answer correct (eliminating 'matches > 0')."""
    question = BenchmarkQuestionV2(
        id="q_1hop_02",
        question="What primary model architecture is proposed in the RAG paper?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="The RAG paper proposes RAG-Sequence and RAG-Token architectures combining a retriever with a generator.",
        required_facts=[
            RequiredFact(id="q2_f1", fact="RAG-Sequence model", weight=1.0, aliases=["rag-sequence", "rag sequence"]),
            RequiredFact(id="q2_f2", fact="RAG-Token model", weight=1.0, aliases=["rag-token", "rag token"]),
            RequiredFact(id="q2_f3", fact="Combines retriever and generator", weight=1.0, aliases=["retriever", "generator"]),
        ],
    )
    # This answer has the single keyword 'generator' from a completely incorrect context
    wrong_answer_with_one_keyword = (
        "The paper evaluated a steam turbine power generator used in electrical engineering."
    )
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=wrong_answer_with_one_keyword,
        retrieved_chunk_ids=["chunk_wrong_01"],
        retrieved_chunk_texts=["Steam turbine generator."],
        citations=["chunk_wrong_01"],
    )

    # Under matches > 0, this would have returned True. Under fact coverage, it fails:
    assert audit.fact_score < 0.50
    assert audit.facts_correct == 1
    assert audit.facts_missing == 2
    assert audit.answerable_correct is False
    assert audit.answerable_incorrect is True


def test_no_question_id_hardcoding_dependency(evaluator, sample_answerable_question):
    """6. Scores depend strictly on content and facts, not question IDs."""
    cloned_question = sample_answerable_question.model_copy(update={"id": "arbitrary_custom_id_999"})
    answer = "The primary authors are Patrick Lewis, Vladimir Karpukhin, and Barlas Oguz."

    audit_original = evaluator.evaluate_question(
        question=sample_answerable_question,
        generated_answer=answer,
        retrieved_chunk_ids=["chunk_dpr_01"],
        retrieved_chunk_texts=["DPR paper authors."],
        citations=["chunk_dpr_01"],
    )
    audit_cloned = evaluator.evaluate_question(
        question=cloned_question,
        generated_answer=answer,
        retrieved_chunk_ids=["chunk_dpr_01"],
        retrieved_chunk_texts=["DPR paper authors."],
        citations=["chunk_dpr_01"],
    )

    assert audit_original.fact_score == audit_cloned.fact_score
    assert audit_original.answerable_correct == audit_cloned.answerable_correct


def test_lexical_chunk_overlap_not_semantic_utilization():
    """7. Lexical chunk overlap is a lexical proxy that does not imply semantic answer correctness."""
    retrieved_chunks = [
        "Dense Passage Retrieval is evaluated on Natural Questions using Wikipedia passages."
    ]
    # Word salad containing tokens from chunks but stating nonsense
    word_salad = "Evaluated passages Wikipedia on Dense Retrieval Natural Questions."
    overlap = compute_lexical_chunk_overlap(word_salad, retrieved_chunks)

    # Overlap is high because all words appear in the chunk
    assert overlap >= 0.80

    # But token F1 against the true reference answer is low
    clean_reference = "DPR was evaluated on the Natural Questions benchmark against Wikipedia."
    f1 = compute_token_f1(word_salad, clean_reference)
    assert f1 < 0.60


def test_valid_citation_ids_not_hallucinations(evaluator):
    """8. Valid cited IDs existing in retrieved chunks yield 0.0 invalid citation rate."""
    citations = ["chunk_01", "chunk_02"]
    retrieved_chunk_ids = ["chunk_01", "chunk_02", "chunk_03"]
    invalid_rate = evaluator.evaluate_citations(citations, retrieved_chunk_ids)
    assert invalid_rate == 0.0


def test_missing_retrieval_ground_truth_is_not_perfect(evaluator, sample_unanswerable_question):
    """Missing retrieval labels must be N/A, never synthetic 1.0 scores."""
    metrics = evaluator.evaluate_retrieval(["chunk_01"], [])
    assert metrics["evaluable"] is False
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["mrr"] is None


def test_explicit_contradiction_is_not_counted_as_fact(evaluator):
    """An answer explicitly negating a required fact must be marked incorrect."""
    question = BenchmarkQuestionV2(
        id="q_contra",
        question="Who authored DPR?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="Vladimir Karpukhin authored DPR.",
        required_facts=[RequiredFact(id="author", fact="Vladimir Karpukhin is an author", aliases=["vladimir karpukhin"])],
        gold_chunk_ids=["chunk_01"],
    )
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer="Vladimir Karpukhin is not an author of the DPR paper.",
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["Vladimir Karpukhin is an author of DPR."],
        citations=["chunk_01"],
    )
    assert audit.fact_score == 0.0
    assert audit.facts_incorrect == 1
    assert audit.incorrect_fact_ids == ["author"]
    assert audit.answerable_correct is False


def test_graph_provenance_ids_are_valid_evidence(evaluator):
    """A citation may refer to graph provenance as well as vector chunks."""
    question = BenchmarkQuestionV2(
        id="q_graph",
        question="Which entity is linked?",
        hop_type=EvalHopTypeV2.TWO_HOP,
        answerable=True,
        reference_answer="A is linked to B.",
        required_facts=[RequiredFact(id="f1", fact="A is linked to B", aliases=["a is linked to b"])],
        gold_chunk_ids=["chunk_01"],
    )
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer="A is linked to B [chunk_graph_01].",
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["A and B are related."],
        citations=["chunk_graph_01"],
        available_evidence_ids=["chunk_01", "chunk_graph_01"],
    )
    assert audit.invalid_citation_reference_rate == 0.0


def test_unanswerable_questions_are_excluded_from_fact_score(evaluator, sample_unanswerable_question):
    """Unanswerable items use abstention scoring, not factual-answer scoring."""
    audit = evaluator.evaluate_question(
        question=sample_unanswerable_question,
        generated_answer="I cannot answer because there is insufficient evidence.",
        retrieved_chunk_ids=[],
        retrieved_chunk_texts=[],
        citations=[],
    )
    assert audit.fact_evaluable is False
    assert audit.fact_score is None
    assert audit.facts_total == 0
    assert audit.correctly_abstained is True


def test_invalid_citation_ids_detected(evaluator):
    """9. Fabricated or unretrieved cited IDs are flagged in invalid_citation_reference_rate."""
    citations = ["chunk_01", "chunk_hallucinated_99"]
    retrieved_chunk_ids = ["chunk_01", "chunk_02"]
    invalid_rate = evaluator.evaluate_citations(citations, retrieved_chunk_ids)
    assert invalid_rate == 0.50


def test_concluding_hedge_does_not_zero_satisfied_facts():
    """Safeguard 1: Refusal/hedge cue must never erase already-satisfied facts."""
    evaluator = EvaluatorV2(enable_semantic_judge=False)
    question = BenchmarkQuestionV2(
        id="q_agg_test",
        question="How do GraphRAG-Bench and IslamicFaithQA compare?",
        hop_type=EvalHopTypeV2.AGGREGATION,
        answerable=True,
        reference_answer="GraphRAG-Bench evaluates hierarchical retrieval while IslamicFaithQA measures hallucination.",
        required_facts=[
            RequiredFact(id="f1", fact="GraphRAG-Bench evaluates hierarchical knowledge retrieval", aliases=["graphrag-bench", "hierarchical knowledge retrieval"]),
            RequiredFact(id="f2", fact="IslamicFaithQA measures hallucination and abstention", aliases=["islamicfaithqa", "hallucination"]),
        ],
        gold_chunk_ids=["chunk_01", "chunk_02"],
    )
    # Both facts are asserted, followed by a concluding comparative disclaimer
    hedged_answer = (
        "GraphRAG-Bench is designed to evaluate GraphRAG models on hierarchical knowledge retrieval [chunk_01]. "
        "In contrast, IslamicFaithQA focuses on measuring hallucination and abstention [chunk_02]. "
        "However, the provided evidence is insufficient to establish a direct comparison between the two objectives."
    )
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=hedged_answer,
        retrieved_chunk_ids=["chunk_01", "chunk_02"],
        retrieved_chunk_texts=["Text"],
        citations=["chunk_01", "chunk_02"],
    )

    assert audit.fact_score == 1.0
    assert audit.facts_correct == 2
    assert audit.facts_missing == 0
    assert audit.facts_incorrect == 0
    assert audit.did_not_abstain is True
    assert audit.incorrectly_abstained is False
    assert audit.answerable_correct is True


def test_pure_refusal_with_zero_facts_is_genuine_abstention():
    """Safeguard 1: Pure refusal with 0 satisfied facts on an answerable question remains an abstention."""
    evaluator = EvaluatorV2(enable_semantic_judge=False)
    question = BenchmarkQuestionV2(
        id="q_ans_refuse",
        question="Who authored the DPR paper?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="Vladimir Karpukhin authored DPR.",
        required_facts=[
            RequiredFact(id="f1", fact="Vladimir Karpukhin is an author", aliases=["vladimir karpukhin"]),
        ],
        gold_chunk_ids=["chunk_01"],
    )
    pure_refusal = "I don't have enough information to answer this question because the corpus lacks evidence."
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=pure_refusal,
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["Text"],
        citations=[],
    )

    assert audit.fact_score == 0.0
    assert audit.facts_correct == 0
    assert audit.facts_missing == 1
    assert audit.did_not_abstain is False
    assert audit.incorrectly_abstained is True
    assert audit.answerable_correct is False


def test_semantic_fallback_per_fact_with_isolated_inputs():
    """Safeguards 2 & 4: Per-fact semantic judge fallback with strict context isolation."""
    recorded_calls = []

    class MockPerFactJudge:
        def judge_atomic_fact(self, question: str, generated_answer: str, atomic_fact: str):
            recorded_calls.append({
                "question": question,
                "answer": generated_answer,
                "fact": atomic_fact,
            })
            if "imperfect knowledge graphs" in atomic_fact:
                return {
                    "status": "entailed",
                    "method": "semantic_judge",
                    "contradicted": False,
                    "judge_score": 0.95,
                    "reasoning": "Paraphrase verified semantically",
                }
            return {
                "status": "unsupported",
                "method": "semantic_judge",
                "contradicted": False,
                "judge_score": 0.0,
                "reasoning": "Unsupported claim",
            }

    mock_judge = MockPerFactJudge()
    evaluator = EvaluatorV2(judge_backend=mock_judge, enable_semantic_judge=True)

    question = BenchmarkQuestionV2(
        id="q_2hop_mock",
        question="What issue modes occur in LLM-constructed KGs?",
        hop_type=EvalHopTypeV2.TWO_HOP,
        answerable=True,
        reference_answer="Secret reference answer that judge must NEVER see.",
        required_facts=[
            RequiredFact(id="f1", fact="Hallucination from imperfect knowledge graphs", aliases=["strict_string_12345"]),
        ],
        gold_chunk_ids=["secret_gold_chunk_99"],
    )

    # Generated answer uses semantic paraphrase rather than the strict alias
    answer = "The study demonstrates that spurious noise and flawed graph topologies lead to hallucinations."
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=answer,
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["Text"],
        citations=["chunk_01"],
    )

    # Verify per-fact call isolation (Safeguard 2)
    assert len(recorded_calls) == 1
    call = recorded_calls[0]
    assert call["question"] == question.question
    assert call["answer"] == answer
    assert call["fact"] == "Hallucination from imperfect knowledge graphs"
    # Ground truth must NOT leak
    assert "Secret reference answer" not in str(call)
    assert "secret_gold_chunk_99" not in str(call)

    # Verify scores and evidence trail (Safeguards 2 & 4)
    assert audit.fact_score == 1.0
    assert audit.facts_correct == 1
    assert len(audit.fact_verdicts) == 1
    v = audit.fact_verdicts[0]
    assert v["fact_id"] == "f1"
    assert v["status"] == "entailed"
    assert v["method"] == "semantic_judge"
    assert v["lexical_match"] is False
    assert v["contradicted"] is False
    assert v["judge_score"] == 0.95


def test_semantic_judge_contradiction_overrides_entailment():
    """Safeguard 3: Contradiction must override entailment in semantic evaluation."""
    class MockContradictionJudge:
        def judge_atomic_fact(self, question: str, generated_answer: str, atomic_fact: str):
            return {
                "status": "contradicted",
                "method": "semantic_judge",
                "contradicted": True,
                "judge_score": 0.0,
                "reasoning": "The answer directly contradicts the atomic fact.",
            }

    evaluator = EvaluatorV2(judge_backend=MockContradictionJudge(), enable_semantic_judge=True)
    question = BenchmarkQuestionV2(
        id="q_contra_mock",
        question="Did Vladimir Karpukhin author DPR?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="Vladimir Karpukhin authored DPR.",
        required_facts=[
            RequiredFact(id="f1", fact="Vladimir Karpukhin is an author of DPR", aliases=["none_matching"]),
        ],
        gold_chunk_ids=["chunk_01"],
    )
    answer = "The publication clarifies that Vladimir Karpukhin was not involved in DPR."
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=answer,
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["Text"],
        citations=["chunk_01"],
    )

    assert audit.fact_score == 0.0
    assert audit.facts_correct == 0
    assert audit.facts_incorrect == 1
    assert audit.incorrect_fact_ids == ["f1"]
    assert len(audit.fact_verdicts) == 1
    assert audit.fact_verdicts[0]["status"] == "contradicted"
    assert audit.fact_verdicts[0]["contradicted"] is True


def test_evidence_trail_schema():
    """Safeguard 4: Verify full structure of fact_verdicts evidence trail."""
    evaluator = EvaluatorV2(enable_semantic_judge=False)
    question = BenchmarkQuestionV2(
        id="q_trail_test",
        question="Who authored DPR?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="Vladimir Karpukhin and Patrick Lewis.",
        required_facts=[
            RequiredFact(id="f1", fact="Vladimir Karpukhin is an author", aliases=["vladimir karpukhin"]),
            RequiredFact(id="f2", fact="Patrick Lewis is an author", aliases=["patrick lewis"]),
        ],
        gold_chunk_ids=["chunk_01"],
    )
    # f1 satisfied, f2 negated
    answer = "Vladimir Karpukhin is an author. However, Patrick Lewis is not an author."
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=answer,
        retrieved_chunk_ids=["chunk_01"],
        retrieved_chunk_texts=["Text"],
        citations=["chunk_01"],
    )

    assert len(audit.fact_verdicts) == 2
    f1_v = next(v for v in audit.fact_verdicts if v["fact_id"] == "f1")
    assert f1_v["status"] == "entailed"
    assert f1_v["lexical_match"] is True
    assert f1_v["contradicted"] is False
    assert f1_v["judge_score"] == 1.0

    f2_v = next(v for v in audit.fact_verdicts if v["fact_id"] == "f2")
    assert f2_v["status"] == "contradicted"
    assert f2_v["lexical_match"] is True
    assert f2_v["contradicted"] is True
    assert f2_v["judge_score"] == 0.0


def test_live_semantic_judge_integration():
    """Live Integration: verify configured endpoint evaluates semantic paraphrase per-fact without leaking reference answer."""
    from src.core.config import get_settings
    settings = get_settings()
    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-dummy") or settings.llm_api_key == "your_api_key_here":
        pytest.skip("LLM API key not configured for live integration test")

    evaluator = EvaluatorV2(enable_semantic_judge=True)
    question = BenchmarkQuestionV2(
        id="q_live_integration",
        question="What failure mode affects GraphRAG constructed by LLMs?",
        hop_type=EvalHopTypeV2.TWO_HOP,
        answerable=True,
        reference_answer="Classified reference answer that must NEVER be passed to the judge.",
        required_facts=[
            RequiredFact(
                id="rf_live",
                fact="Hallucination from imperfect knowledge graphs",
                aliases=["synthetic_unique_alias_xyz_999"],
            ),
        ],
        gold_chunk_ids=["chunk_gold_secret_123"],
    )
    # Uses semantic phrasing; deliberately avoids alias
    generated_answer = "Yizhuo Ma et al. identify two recurring knowledge graph issue modes: spurious noise and incomplete information."
    audit = evaluator.evaluate_question(
        question=question,
        generated_answer=generated_answer,
        retrieved_chunk_ids=["chunk_gold_secret_123"],
        retrieved_chunk_texts=["Text"],
        citations=["chunk_gold_secret_123"],
    )

    assert audit.fact_score == 1.0
    assert audit.facts_correct == 1
    assert len(audit.fact_verdicts) == 1
    verdict = audit.fact_verdicts[0]
    assert verdict["fact_id"] == "rf_live"
    assert verdict["status"] == "entailed"
    assert verdict["method"] == "semantic_judge"
    assert verdict["lexical_match"] is False
    assert verdict["contradicted"] is False
    assert verdict["judge_score"] >= 0.70


def test_graph_provenance_does_not_inflate_substantive_or_unified_recall(evaluator):
    """Synthetic test: graph statement contains [chunk: X], while X is deliberately absent from retrieved_chunk_ids.

    Expected:
      - substantive_chunk_recall = 0.0
      - unified_evidence_recall = 0.0
      - graph_provenance_chunk_ids contains 'chunk_X' as diagnostic only
      - graph_fact_recall is None (N/A) since there are no gold graph facts
    """
    from src.eval.models_v2 import GoldEvidenceItem, GoldEvidenceType
    question = BenchmarkQuestionV2(
        id="q_synth_provenance_01",
        question="What method is evaluated?",
        hop_type=EvalHopTypeV2.ONE_HOP,
        answerable=True,
        reference_answer="Method X is evaluated.",
        required_facts=[
            RequiredFact(id="f1", fact="Method X is evaluated", weight=1.0, aliases=["method x"]),
        ],
        gold_chunk_ids=["chunk_X"],
        gold_evidence=[
            GoldEvidenceItem(id="chunk_X", type=GoldEvidenceType.CHUNK, supports=["f1"]),
        ],
    )
    # The graph statements cite [chunk: chunk_X], but chunk_X text passage was NEVER retrieved!
    graph_facts = [
        "Entity 'GraphRAG' -[:USES_METHOD]- 'Method X' (Method) [chunk: chunk_X].",
    ]
    graph_provenance_ids = ["chunk_X"]

    audit = evaluator.evaluate_question(
        question=question,
        generated_answer="Method X is evaluated.",
        retrieved_chunk_ids=["chunk_other_unrelated"],
        retrieved_chunk_texts=["Unrelated passage text."],
        citations=[],
        graph_evidence_ids=graph_provenance_ids,
        graph_provenance_chunk_ids=graph_provenance_ids,
        graph_facts=graph_facts,
    )

    assert audit.substantive_chunk_recall == 0.0
    assert audit.unified_evidence_recall == 0.0
    assert "chunk_X" in audit.graph_provenance_chunk_ids
    assert audit.graph_fact_recall is None


