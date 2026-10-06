from __future__ import annotations

from typing import Any, Optional

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend

_FAITHFULNESS_PROMPT = """You are grading whether an answer is faithful to the given context: every \
claim in the answer must be supported by the context, with no fabrication.

Context:
{context}

Answer:
{answer}

Score faithfulness from 0.0 (answer contains claims not supported by the context) \
to 1.0 (every claim is directly supported by the context). Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""

_CONTEXT_PRECISION_PROMPT = """You are grading how relevant the retrieved context is to answering the \
question below. Irrelevant or off-topic passages lower the score.

Question:
{question}

Retrieved context:
{context}

Score context precision from 0.0 (mostly irrelevant) to 1.0 (all retrieved context \
is relevant to answering the question). Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""

_CONTEXT_RECALL_PROMPT = """You are grading whether the retrieved context contains all the necessary \
information and factual claims present in the reference answer to answer the question.

Question:
{question}

Reference answer:
{reference}

Retrieved context:
{context}

Score context recall from 0.0 (retrieved context misses key reference information) \
to 1.0 (retrieved context covers all necessary information from the reference). \
Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""

_ANSWER_RELEVANCY_PROMPT = """You are grading whether an answer actually addresses the question asked, \
independent of whether the answer is factually correct.

Question:
{question}

Answer:
{answer}

Score answer relevancy from 0.0 (does not address the question) to 1.0 (directly \
and completely addresses it). Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""

_ANSWER_CORRECTNESS_PROMPT = """You are grading the factual correctness of a generated answer \
compared against a ground-truth reference answer.

Question:
{question}

Ground-truth reference:
{reference}

Generated answer:
{answer}

Score answer correctness from 0.0 (completely inaccurate or contradictory to reference) \
to 1.0 (factually accurate and aligns with the ground-truth reference). \
Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""


class RagEvaluator(BaseEvaluator):
    """RAG evaluator: faithfulness, context_precision, context_recall, answer_relevancy,
    answer_correctness, and hallucination_rate.
    """

    ALL_METRICS = (
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevancy",
        "answer_correctness",
        "hallucination_rate",
    )

    METRIC_DESCRIPTIONS = {
        "faithfulness": (
            "LLM judge scores 0.0-1.0: does every claim in the answer trace back "
            "to the retrieved context, with no fabrication?"
        ),
        "context_precision": (
            "LLM judge scores 0.0-1.0: how much of the retrieved context is "
            "actually relevant to answering the question (irrelevant passages lower it)?"
        ),
        "context_recall": (
            "LLM judge scores 0.0-1.0: does the retrieved context contain the information "
            "necessary to support the reference answer?"
        ),
        "answer_relevancy": (
            "LLM judge scores 0.0-1.0: does the answer address the question asked, "
            "independent of whether it's factually correct?"
        ),
        "answer_correctness": (
            "LLM judge scores 0.0-1.0: does the generated answer factually agree with "
            "the ground-truth reference answer?"
        ),
        "hallucination_rate": (
            "1.0 - faithfulness, same underlying judge call reused (no extra API cost)."
        ),
    }

    def __init__(self, judge: BaseJudgeBackend, metrics: Optional[list[str]] = None) -> None:
        self.judge = judge
        self.metrics = metrics or list(self.ALL_METRICS)

    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        context_text = "\n---\n".join(context or []) or "(no context retrieved)"
        scores: dict[str, float] = {}

        needs_faithfulness = "faithfulness" in self.metrics or "hallucination_rate" in self.metrics
        if needs_faithfulness:
            faithfulness = self.judge.score(
                _FAITHFULNESS_PROMPT.format(context=context_text, answer=output)
            )
            if "faithfulness" in self.metrics:
                scores["faithfulness"] = faithfulness
            if "hallucination_rate" in self.metrics:
                scores["hallucination_rate"] = 1.0 - faithfulness

        if "context_precision" in self.metrics:
            scores["context_precision"] = self.judge.score(
                _CONTEXT_PRECISION_PROMPT.format(question=example_input, context=context_text)
            )

        if "context_recall" in self.metrics and reference:
            scores["context_recall"] = self.judge.score(
                _CONTEXT_RECALL_PROMPT.format(
                    question=example_input, reference=reference, context=context_text
                )
            )

        if "answer_relevancy" in self.metrics:
            scores["answer_relevancy"] = self.judge.score(
                _ANSWER_RELEVANCY_PROMPT.format(question=example_input, answer=output)
            )

        if "answer_correctness" in self.metrics and reference:
            scores["answer_correctness"] = self.judge.score(
                _ANSWER_CORRECTNESS_PROMPT.format(
                    question=example_input, reference=reference, answer=output
                )
            )

        return scores

