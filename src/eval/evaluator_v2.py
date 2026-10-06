# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
Decoupled 5-Layer Evaluation Engine (V2).

Architecture Role:
    Core measurement engine for the Evaluation-Integrity Refactor (V2).
    Separates evaluation into 5 distinct, decoupled layers:
      1. Layer A: Retrieval Correctness (Precision@K, Recall@K, MRR - evaluable only with gold chunk IDs)
      2. Layer B: Factual Answer Correctness (Weighted Required-Fact Coverage with negation detection)
      3. Layer C: Context Groundedness (LLM-Judge Groundedness, Unsupported Claim Rate, explicit method logging)
      4. Layer D: Answerability / Abstention (Decoupled Did-Not-Abstain and Correct Abstention Classification)
      5. Layer E: Efficiency (Latency, Token Usage, Cost)

    Strict Design Principles:
      - Zero Data Leakage: Groundedness judge NEVER receives gold reference data or required facts.
      - Lexical Proxies: Token F1 and chunk overlap are explicitly labeled as lexical heuristics.
      - No Hardcoded Overrides: All scores are computed deterministically or via judge calls.
      - Full Provenance: Generates QuestionAuditRecord with raw chunks, text, and scores.
      - Evidence Inclusion: Validates citations against combined vector and graph provenance IDs.

Inputs:
    - BenchmarkQuestionV2 specification (with atomic weighted facts, gold chunk IDs, answerability flag).
    - Pipeline output: generated answer, citations, retrieved chunks, graph facts, latency.

Outputs:
    - QuestionAuditRecord containing granular Layer A-E metrics and audit evidence.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from src.eval.models_v2 import BenchmarkQuestionV2, GoldEvidenceItem, GoldEvidenceType, QuestionAuditRecord
from src.eval.text_norm import normalize_text

logger = logging.getLogger(__name__)

_REFUSAL_CUES = [
    "insufficient evidence",
    "cannot answer",
    "lacks sufficient evidence",
    "no sufficient evidence",
    "no evidence in the",
    "not mentioned in the corpus",
    "outside the scope",
    "does not contain evidence",
    "unanswerable",
    "not found in the corpus",
    "lacks evidence",
    "no evidence provided",
]

FACTUAL_CORRECTNESS_THRESHOLD = 0.70

_NEGATION_PREFIXES = (
    "not ",
    "no ",
    "never ",
    "without ",
    "did not ",
    "does not ",
    "do not ",
    "was not ",
    "were not ",
    "is not ",
    "are not ",
    "wasn't ",
    "weren't ",
    "isn't ",
    "aren't ",
)


def is_refusal(text: str) -> bool:
    norm = normalize_text(text)
    if not norm:
        return True
    return any(cue in norm for cue in _REFUSAL_CUES)


def tokenize_words(text: str) -> List[str]:
    norm = normalize_text(text)
    cleaned = re.sub(r"[^\w\s\-]", "", norm)
    return cleaned.split()


def compute_token_f1(prediction: str, reference: str) -> float:
    """Token overlap against a clean reference answer; never factual accuracy."""
    pred_tokens = tokenize_words(prediction)
    ref_tokens = tokenize_words(reference)
    if not pred_tokens or not ref_tokens:
        return 1.0 if pred_tokens == ref_tokens else 0.0
    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(ref_tokens)
    return round((2.0 * precision * recall) / (precision + recall), 4)


def compute_lexical_chunk_overlap(answer: str, chunk_texts: List[str]) -> float:
    """Lexical answer/context overlap; does not imply evidence use or correctness."""
    ans_tokens = set(tokenize_words(answer))
    if not ans_tokens:
        return 0.0
    all_chunk_tokens: Set[str] = set()
    for text in chunk_texts:
        all_chunk_tokens.update(tokenize_words(text))
    if not all_chunk_tokens:
        return 0.0
    overlap = ans_tokens & all_chunk_tokens
    return round(len(overlap) / len(ans_tokens), 4)


def _is_negated_occurrence(answer: str, phrase: str) -> bool:
    """Conservative local contradiction detector for explicit negation."""
    if not phrase:
        return False
    start = answer.find(phrase)
    while start >= 0:
        before = answer[max(0, start - 48):start]
        clause_before = re.split(r"[.;!?\n]", before)[-1]
        if any(clause_before.strip().endswith(prefix.strip()) or re.search(r"\bnot\s+$", clause_before) for prefix in _NEGATION_PREFIXES):
            return True
        if re.search(r"\b(?:is|was|are|were|did|does|do)\s+not\b", clause_before):
            return True

        after = answer[start + len(phrase):min(len(answer), start + len(phrase) + 32)]
        clause_after = re.split(r"[.;!?\n]", after)[0]
        if re.search(r"^\s*(?:is|was|are|were|did|does|do)?\s*(?:not|never)\b", clause_after):
            return True
        start = answer.find(phrase, start + 1)
    return False


class EvaluatorV2:
    def __init__(
        self,
        judge_backend: Any = None,
        judge_model: Optional[str] = None,
        enable_semantic_judge: bool = True,
    ) -> None:
        self.judge_backend = judge_backend
        self._judge_model = judge_model
        self.enable_semantic_judge = enable_semantic_judge
        self._llm_client: Optional[Any] = None

    def _get_llm_client(self) -> Optional[Any]:
        if not self.enable_semantic_judge:
            return None
        if self._llm_client is not None:
            return self._llm_client
        try:
            from openai import OpenAI
            from src.core.config import get_settings

            settings = get_settings()
            api_key = settings.llm_api_key
            if not api_key or api_key.startswith("sk-dummy") or api_key == "your_api_key_here":
                return None
            self._llm_client = OpenAI(
                base_url=settings.llm_base_url,
                api_key=api_key,
                timeout=settings.request_timeout_seconds,
            )
            if not self._judge_model:
                self._judge_model = settings.synthesis_model
            return self._llm_client
        except Exception as exc:
            logger.debug("Could not initialize OpenAI client for EvaluatorV2: %s", exc)
            return None

    def _verify_atomic_fact_semantically(
        self,
        question: str,
        generated_answer: str,
        atomic_fact: str,
    ) -> Dict[str, Any]:
        """Judge whether a single atomic fact is entailed, contradicted, or unsupported.

        CRITICAL LEAKAGE RESTRICTIONS (Safeguard 2):
        The judge receives ONLY:
          1. The user Question
          2. The Generated Answer
          3. The single Atomic Fact being tested
        It NEVER receives reference_answer, other required facts, gold chunk IDs, or labels.
        """
        # 1. Custom judge backend implementing judge_atomic_fact directly
        if self.judge_backend is not None and hasattr(self.judge_backend, "judge_atomic_fact"):
            try:
                res = self.judge_backend.judge_atomic_fact(question, generated_answer, atomic_fact)
                if isinstance(res, dict) and "status" in res:
                    return res
            except Exception as exc:
                logger.warning("judge_backend.judge_atomic_fact failed: %s", exc)

        # 2. BaseJudgeBackend with score(prompt)
        if self.judge_backend is not None and hasattr(self.judge_backend, "score") and not hasattr(self.judge_backend, "chat"):
            prompt = (
                "You are an impartial evaluation judge for factual entailment.\n"
                f"Question: {question}\n"
                f"Generated Answer: {generated_answer}\n"
                f"Atomic Fact: {atomic_fact}\n\n"
                "Does the Generated Answer entail the Atomic Fact? "
                "Return 1.0 for entailed, 0.0 for unsupported or contradicted."
            )
            try:
                sc = float(self.judge_backend.score(prompt))
                if sc >= 0.70:
                    return {
                        "status": "entailed",
                        "method": "semantic_judge",
                        "contradicted": False,
                        "judge_score": round(sc, 4),
                        "reasoning": f"Judge backend scored {sc}",
                    }
                else:
                    return {
                        "status": "unsupported",
                        "method": "semantic_judge",
                        "contradicted": False,
                        "judge_score": round(sc, 4),
                        "reasoning": f"Judge backend scored {sc}",
                    }
            except Exception as exc:
                logger.warning("judge_backend.score failed: %s", exc)

        # 3. Direct LLM Client
        client = self._get_llm_client()
        if not client:
            return {
                "status": "unsupported",
                "method": "lexical_miss_no_judge",
                "contradicted": False,
                "judge_score": 0.0,
                "reasoning": "Semantic judge inactive or unavailable",
            }

        prompt = (
            "You are an impartial Natural Language Inference judge evaluating whether a generated answer "
            "entails, contradicts, or leaves unsupported a specific atomic fact.\n"
            "Do not use external knowledge. Rely ONLY on the generated answer.\n\n"
            f"QUESTION:\n{question}\n\n"
            f"GENERATED ANSWER:\n{generated_answer}\n\n"
            f"ATOMIC FACT BEING TESTED:\n{atomic_fact}\n\n"
            "EVALUATION CRITERIA:\n"
            "- \"ENTAILED\": The generated answer semantically asserts or confirms this specific atomic fact "
            "(including paraphrases, synonyms, or direct logical equivalents).\n"
            "- \"CONTRADICTED\": The generated answer explicitly denies, negates, or refutes this atomic fact.\n"
            "- \"UNSUPPORTED\": The generated answer does not mention, leaves uncertain, expresses ignorance about "
            "(\"I don't know\", \"insufficient evidence\"), or does not provide enough information to confirm or deny this fact.\n\n"
            "RULES:\n"
            "1. Base your evaluation ONLY on what the Generated Answer states.\n"
            "2. If the answer explicitly states the fact is false, return \"CONTRADICTED\".\n"
            "3. If the answer merely hedges that evidence is insufficient or lacks the fact, return \"UNSUPPORTED\".\n"
            "4. Respond strictly in valid JSON format:\n"
            '{"verdict": "ENTAILED" | "CONTRADICTED" | "UNSUPPORTED", "judge_score": <float 0.0-1.0>, "reasoning": "<short explanation>"}'
        )

        try:
            model = self._judge_model or "meta/llama-3.2-11b-vision-instruct"
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=120,
            )
            raw = response.choices[0].message.content or ""
            data = None
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
            try:
                data = json.loads(cleaned)
            except Exception:
                pass

            if not data:
                first_brace = raw.find("{")
                last_brace = raw.rfind("}")
                if first_brace != -1 and last_brace > first_brace:
                    try:
                        data = json.loads(raw[first_brace : last_brace + 1])
                    except Exception:
                        pass

            if not data:
                v_match = re.search(r"\b(ENTAILED|CONTRADICTED|UNSUPPORTED)\b", raw, re.IGNORECASE)
                if v_match:
                    verdict_word = v_match.group(1).upper()
                    data = {
                        "verdict": verdict_word,
                        "judge_score": 1.0 if verdict_word == "ENTAILED" else 0.0,
                        "reasoning": raw[:120].strip(),
                    }

            if data and isinstance(data, dict):
                verdict = str(data.get("verdict", "")).strip().upper()
                score = float(data.get("judge_score", 1.0 if verdict == "ENTAILED" else 0.0))
                reasoning = str(data.get("reasoning", ""))
                if verdict == "ENTAILED" and score >= 0.70:
                    return {
                        "status": "entailed",
                        "method": "semantic_judge",
                        "contradicted": False,
                        "judge_score": round(score, 4),
                        "reasoning": reasoning,
                    }
                elif verdict == "CONTRADICTED":
                    return {
                        "status": "contradicted",
                        "method": "semantic_judge",
                        "contradicted": True,
                        "judge_score": 0.0,
                        "reasoning": reasoning,
                    }
                else:
                    return {
                        "status": "unsupported",
                        "method": "semantic_judge",
                        "contradicted": False,
                        "judge_score": 0.0,
                        "reasoning": reasoning,
                    }
        except Exception as exc:
            logger.debug("Semantic judge evaluation exception: %s", exc)

        return {
            "status": "unsupported",
            "method": "semantic_judge_error",
            "contradicted": False,
            "judge_score": 0.0,
            "reasoning": "Judge execution failed or returned invalid response",
        }

    def evaluate_retrieval(
        self,
        retrieved_chunk_ids: List[str],
        gold_chunk_ids: List[str],
    ) -> Dict[str, Any]:
        """Return None-valued metrics when retrieval ground truth is unavailable."""
        gold_set = set(gold_chunk_ids)
        if not gold_set:
            return {
                "evaluable": False,
                "precision": None,
                "recall": None,
                "mrr": None,
            }

        retrieved_set = set(retrieved_chunk_ids)
        hits = retrieved_set & gold_set
        precision = len(hits) / len(retrieved_chunk_ids) if retrieved_chunk_ids else 0.0
        recall = len(hits) / len(gold_set)
        mrr = 0.0
        for rank, cid in enumerate(retrieved_chunk_ids, start=1):
            if cid in gold_set:
                mrr = 1.0 / rank
                break
        return {
            "evaluable": True,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "mrr": round(mrr, 4),
        }

    def evaluate_facts(
        self,
        question: BenchmarkQuestionV2,
        generated_answer: str,
        available_evidence_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compute weighted required-fact coverage using two-stage verification:

        Stage 1: Normalized lexical/alias match with local negation check.
        Stage 2: Per-fact semantic judge for any candidate that misses lexical match.

        Strict Safeguards:
        1. Refusal never erases already-satisfied facts (answer -> facts -> contradiction -> refusal).
        2. Semantic judge is per-fact with zero ground truth leakage.
        3. Contradiction overrides entailment.
        4. Detailed fact_verdicts evidence trail preserved with per-fact evidence support check.
        """
        norm_ans = normalize_text(generated_answer)

        if not question.answerable:
            return {
                "fact_evaluable": False,
                "fact_score": None,
                "facts_correct": 0,
                "facts_missing": 0,
                "facts_incorrect": 0,
                "facts_total": 0,
                "fact_coverage": None,
                "satisfied_fact_ids": [],
                "missing_fact_ids": [],
                "incorrect_fact_ids": [],
                "fact_verdicts": [],
            }

        total_weight = sum(f.weight for f in question.required_facts)
        if total_weight <= 0:
            raise ValueError(f"Question {question.id} has no positive-weight required facts")

        satisfied_weight = 0.0
        satisfied: List[str] = []
        missing: List[str] = []
        incorrect: List[str] = []
        fact_verdicts: List[Dict[str, Any]] = []

        for rf in question.required_facts:
            candidates = sorted({rf.fact, *rf.aliases}, key=len, reverse=True)
            positive_lexical = False
            lexical_negated = False
            matched_cand = None

            for cand in candidates:
                norm_cand = normalize_text(cand)
                if not norm_cand or norm_cand not in norm_ans:
                    continue
                if _is_negated_occurrence(norm_ans, norm_cand):
                    lexical_negated = True
                else:
                    positive_lexical = True
                    matched_cand = cand
                    break

            supporting_ids = [
                e.id for e in getattr(question, "gold_evidence", [])
                if rf.id in getattr(e, "supports", [])
            ]
            evidence_retrieved = (
                any(eid in available_evidence_ids for eid in supporting_ids)
                if (available_evidence_ids is not None and supporting_ids)
                else None
            )

            if lexical_negated:
                # Safeguard 3: Contradiction overrides entailment
                verdict = {
                    "fact_id": rf.id,
                    "fact": rf.fact,
                    "status": "contradicted",
                    "method": "lexical_negation",
                    "lexical_match": True,
                    "contradicted": True,
                    "judge_score": 0.0,
                    "reasoning": f"Local negation detected for candidate '{matched_cand or cand}'",
                    "supporting_evidence_ids": supporting_ids,
                    "evidence_retrieved": evidence_retrieved,
                }
                incorrect.append(rf.id)
                fact_verdicts.append(verdict)
            elif positive_lexical:
                verdict = {
                    "fact_id": rf.id,
                    "fact": rf.fact,
                    "status": "entailed",
                    "method": "lexical_match",
                    "lexical_match": True,
                    "contradicted": False,
                    "judge_score": 1.0,
                    "reasoning": f"Exact/alias match satisfied by '{matched_cand}'",
                    "supporting_evidence_ids": supporting_ids,
                    "evidence_retrieved": evidence_retrieved,
                }
                satisfied.append(rf.id)
                satisfied_weight += rf.weight
                fact_verdicts.append(verdict)
            else:
                # Stage 2: Semantic judge for THIS fact
                judge_res = self._verify_atomic_fact_semantically(
                    question=question.question,
                    generated_answer=generated_answer,
                    atomic_fact=rf.fact,
                )
                verdict = {
                    "fact_id": rf.id,
                    "fact": rf.fact,
                    "status": judge_res.get("status", "unsupported"),
                    "method": judge_res.get("method", "semantic_judge"),
                    "lexical_match": False,
                    "contradicted": judge_res.get("contradicted", False),
                    "judge_score": judge_res.get("judge_score", 0.0),
                    "reasoning": judge_res.get("reasoning", ""),
                    "supporting_evidence_ids": supporting_ids,
                    "evidence_retrieved": evidence_retrieved,
                }
                fact_verdicts.append(verdict)
                if verdict["status"] == "entailed":
                    satisfied.append(rf.id)
                    satisfied_weight += rf.weight
                elif verdict["status"] == "contradicted":
                    incorrect.append(rf.id)
                else:
                    missing.append(rf.id)

        # Safeguard 1: Refusal never erases already-satisfied facts.
        score = round(satisfied_weight / total_weight, 4)

        return {
            "fact_evaluable": True,
            "fact_score": score,
            "facts_correct": len(satisfied),
            "facts_missing": len(missing),
            "facts_incorrect": len(incorrect),
            "facts_total": len(question.required_facts),
            "fact_coverage": score,
            "satisfied_fact_ids": satisfied,
            "missing_fact_ids": missing,
            "incorrect_fact_ids": incorrect,
            "fact_verdicts": fact_verdicts,
        }

    def evaluate_groundedness(self, retrieved_chunk_texts: List[str], generated_answer: str) -> Dict[str, Any]:
        refusal = is_refusal(generated_answer)
        if refusal:
            return {
                "context_groundedness": 1.0,
                "unsupported_claim_rate": 0.0,
                "method": "deterministic_refusal_no_factual_claims",
            }
        if not retrieved_chunk_texts:
            return {
                "context_groundedness": 0.0,
                "unsupported_claim_rate": 1.0,
                "method": "no_context",
            }

        if self.judge_backend and hasattr(self.judge_backend, "score"):
            combined_context = "\n---\n".join(retrieved_chunk_texts[:5])
            prompt = (
                "You are an impartial evaluation judge for context groundedness.\n"
                "Do not use any external knowledge. Do not infer facts from a gold answer.\n"
                "Given ONLY retrieved context and generated answer, estimate the proportion of "
                "factual claims explicitly supported by the context.\n"
                "Return a single number from 0 to 1.\n\n"
                f"RETRIEVED CONTEXT:\n{combined_context}\n\n"
                f"GENERATED ANSWER:\n{generated_answer}\n"
            )
            try:
                score = float(self.judge_backend.score(prompt))
                score = max(0.0, min(1.0, score))
                return {
                    "context_groundedness": round(score, 4),
                    "unsupported_claim_rate": round(1.0 - score, 4),
                    "method": "llm_judge",
                }
            except Exception:
                pass

        overlap = compute_lexical_chunk_overlap(generated_answer, retrieved_chunk_texts)
        groundedness = min(1.0, round(overlap * 1.25, 4))
        return {
            "context_groundedness": groundedness,
            "unsupported_claim_rate": round(1.0 - groundedness, 4),
            "method": "lexical_overlap_heuristic",
        }

    def evaluate_answerability(
        self,
        question: BenchmarkQuestionV2,
        generated_answer: str,
        fact_score: Optional[float],
        facts_correct: int = 0,
    ) -> Dict[str, bool]:
        refusal = is_refusal(generated_answer)
        if question.answerable:
            if facts_correct > 0:
                # Answer provided satisfied facts; concluding hedges do not invalidate answered facts
                correct = fact_score is not None and fact_score >= FACTUAL_CORRECTNESS_THRESHOLD
                return {
                    "abstention_correct": False,
                    "did_not_abstain": True,
                    "answerable_correct": correct,
                    "answerable_incorrect": not correct,
                    "correctly_abstained": False,
                    "incorrectly_abstained": False,
                }
            else:
                # 0 facts satisfied
                if refusal:
                    return {
                        "abstention_correct": False,
                        "did_not_abstain": False,
                        "answerable_correct": False,
                        "answerable_incorrect": True,
                        "correctly_abstained": False,
                        "incorrectly_abstained": True,
                    }
                else:
                    return {
                        "abstention_correct": False,
                        "did_not_abstain": True,
                        "answerable_correct": False,
                        "answerable_incorrect": True,
                        "correctly_abstained": False,
                        "incorrectly_abstained": False,
                    }

        return {
            "abstention_correct": refusal,
            "did_not_abstain": not refusal,
            "answerable_correct": False,
            "answerable_incorrect": not refusal,
            "correctly_abstained": refusal,
            "incorrectly_abstained": False,
        }

    def evaluate_citations(self, citations: List[str], available_evidence_ids: List[str]) -> float:
        if not citations:
            return 0.0
        evidence = set(available_evidence_ids)
        invalid = sum(1 for c in citations if c not in evidence)
        return round(invalid / len(citations), 4)

    def evaluate_question(
        self,
        question: BenchmarkQuestionV2,
        generated_answer: str,
        retrieved_chunk_ids: List[str],
        retrieved_chunk_texts: List[str],
        citations: List[str],
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model_name: str = "",
        judge_model: str = "",
        error_state: Optional[str] = None,
        available_evidence_ids: Optional[List[str]] = None,
        dataset_sha256: str = "",
        graph_evidence_ids: Optional[List[str]] = None,
        graph_facts: Optional[List[str]] = None,
        evidence_texts: Optional[List[str]] = None,
        retrieved_metadata_ids: Optional[List[str]] = None,
        graph_provenance_chunk_ids: Optional[List[str]] = None,
    ) -> QuestionAuditRecord:
        v_ids = list(dict.fromkeys(retrieved_chunk_ids or []))
        prov_ids = list(dict.fromkeys(graph_provenance_chunk_ids or graph_evidence_ids or []))
        g_facts = list(graph_facts or [])
        m_ids = list(dict.fromkeys(retrieved_metadata_ids or []))

        # Substantive evidence pool: strictly actual retrieved document chunks and catalog metadata records.
        # Provenance IDs from graph statements are kept separate as diagnostic only!
        substantive_evidence_ids = list(dict.fromkeys(v_ids + m_ids))

        # Complete citation ledger: any chunk, metadata, or graph provenance ID present in context is valid for citation
        complete_ledger = list(dict.fromkeys((available_evidence_ids or []) + v_ids + m_ids + prov_ids))

        # Groundedness evaluates over the complete context pool (chunk passages + graph fact statements)
        eval_texts = evidence_texts or (retrieved_chunk_texts + g_facts)

        # Partition gold evidence by type
        gold_chunks = [
            e.id for e in getattr(question, "gold_evidence", [])
            if getattr(e.type, "value", e.type) == "chunk"
        ]
        if not gold_chunks and question.gold_chunk_ids:
            gold_chunks = list(question.gold_chunk_ids)

        gold_metadata = [
            e.id for e in getattr(question, "gold_evidence", [])
            if getattr(e.type, "value", e.type) == "metadata"
        ]
        gold_graph = [
            e.id for e in getattr(question, "gold_evidence", [])
            if getattr(e.type, "value", e.type) == "graph_fact"
        ]

        # Separated Layer A evaluations:
        vec_retrieval = self.evaluate_retrieval(v_ids, gold_chunks)
        substantive_chunk_recall = vec_retrieval["recall"]

        meta_retrieval = self.evaluate_retrieval(m_ids, gold_metadata)
        metadata_recall = meta_retrieval["recall"]

        if gold_graph:
            graph_retrieval = self.evaluate_retrieval(g_facts, gold_graph)
            graph_fact_recall = graph_retrieval["recall"]
            graph_evaluable = graph_retrieval["evaluable"]
        else:
            # Safeguard: Do not report 0 when there are no gold graph facts; report N/A (None).
            graph_retrieval = {
                "evaluable": False,
                "precision": None,
                "recall": None,
                "mrr": None,
            }
            graph_fact_recall = None
            graph_evaluable = False

        # Channel-strict Unified Evidence Recall:
        # Measures whether each gold evidence item was retrieved through its legitimate channel.
        gold_ev_list = getattr(question, "gold_evidence", [])
        if gold_ev_list:
            satisfied_items = 0
            for e in gold_ev_list:
                etype = getattr(e.type, "value", e.type)
                if etype == "chunk" and e.id in v_ids:
                    satisfied_items += 1
                elif etype == "metadata" and e.id in m_ids:
                    satisfied_items += 1
                elif etype == "graph_fact" and (e.id in g_facts or any(e.id in f for f in g_facts)):
                    satisfied_items += 1
            unified_recall = round(satisfied_items / len(gold_ev_list), 4) if len(gold_ev_list) > 0 else None
            unified_evaluable = True if len(gold_ev_list) > 0 else False
        elif gold_chunks:
            unified_recall = substantive_chunk_recall
            unified_evaluable = vec_retrieval["evaluable"]
        else:
            unified_recall = None
            unified_evaluable = False

        facts = self.evaluate_facts(question, generated_answer, available_evidence_ids=substantive_evidence_ids)
        grounded = self.evaluate_groundedness(eval_texts, generated_answer)
        answerability = self.evaluate_answerability(
            question,
            generated_answer,
            facts["fact_score"],
            facts_correct=facts["facts_correct"],
        )
        token_f1 = compute_token_f1(generated_answer, question.reference_answer)
        chunk_overlap = compute_lexical_chunk_overlap(generated_answer, eval_texts)
        invalid_citations = self.evaluate_citations(citations, complete_ledger)

        return QuestionAuditRecord(
            question_id=question.id,
            hop_type=question.hop_type.value,
            answerable=question.answerable,
            generated_answer=generated_answer,
            retrieval_evaluable=unified_evaluable,
            retrieval_precision=vec_retrieval["precision"],
            retrieval_recall=unified_recall,
            retrieval_mrr=vec_retrieval["mrr"],
            vector_retrieval_evaluable=vec_retrieval["evaluable"],
            vector_retrieval_precision=vec_retrieval["precision"],
            vector_retrieval_recall=vec_retrieval["recall"],
            vector_retrieval_mrr=vec_retrieval["mrr"],
            substantive_chunk_recall=substantive_chunk_recall,
            graph_retrieval_evaluable=graph_evaluable,
            graph_retrieval_precision=graph_retrieval["precision"],
            graph_retrieval_recall=graph_fact_recall,
            graph_retrieval_mrr=graph_retrieval["mrr"],
            graph_evidence_ids=prov_ids,
            graph_provenance_chunk_ids=prov_ids,
            graph_fact_recall=graph_fact_recall,
            graph_facts=g_facts,
            complete_evidence_ledger=complete_ledger,
            metadata_retrieval_evaluable=meta_retrieval["evaluable"],
            metadata_retrieval_precision=meta_retrieval["precision"],
            metadata_retrieval_recall=metadata_recall,
            metadata_recall=metadata_recall,
            metadata_evidence_ids=m_ids,
            unified_evidence_recall=unified_recall,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieved_chunk_texts=retrieved_chunk_texts,
            available_evidence_ids=substantive_evidence_ids,
            fact_evaluable=facts["fact_evaluable"],
            fact_score=facts["fact_score"],
            facts_correct=facts["facts_correct"],
            facts_missing=facts["facts_missing"],
            facts_incorrect=facts["facts_incorrect"],
            facts_total=facts["facts_total"],
            fact_coverage=facts["fact_coverage"],
            satisfied_fact_ids=facts["satisfied_fact_ids"],
            missing_fact_ids=facts["missing_fact_ids"],
            incorrect_fact_ids=facts["incorrect_fact_ids"],
            fact_verdicts=facts.get("fact_verdicts", []),
            fact_evaluation_method=(
                "hybrid_lexical_semantic_judge"
                if any(v.get("method") == "semantic_judge" for v in facts.get("fact_verdicts", []))
                else "structured_atomic_fact_proxy"
            ),
            context_groundedness=grounded["context_groundedness"],
            unsupported_claim_rate=grounded["unsupported_claim_rate"],
            groundedness_method=grounded["method"],
            judge_model=judge_model,
            abstention_correct=answerability["abstention_correct"],
            did_not_abstain=answerability["did_not_abstain"],
            answerable_correct=answerability["answerable_correct"],
            answerable_incorrect=answerability["answerable_incorrect"],
            correctly_abstained=answerability["correctly_abstained"],
            incorrectly_abstained=answerability["incorrectly_abstained"],
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reference_text_token_f1=token_f1,
            lexical_fact_proxy_token_f1=token_f1,
            lexical_chunk_overlap_utilization=chunk_overlap,
            invalid_citation_reference_rate=invalid_citations,
            model_name=model_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            citations=citations,
            error_state=error_state,
            dataset_sha256=dataset_sha256,
        )
