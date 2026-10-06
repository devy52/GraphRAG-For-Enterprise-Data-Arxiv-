from __future__ import annotations

from typing import Any, Optional

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend

_QUALITY_PROMPT = """Rate the quality of this response to the given input on a 0.0-1.0 scale, \
considering correctness, clarity, and completeness.{reference_block}

Input:
{input}

Response:
{output}

Respond with only the number."""

_FLUENCY_PROMPT = """Rate how natural, grammatical, and readable this text is on a 0.0-1.0 scale, \
independent of whether its content is correct.

Text:
{output}

Respond with only the number."""


class GenericEvaluator(BaseEvaluator):
    """Fallback LLM-judge evaluator for tracks without a specialized module
    yet (chatbots, generic completions, anything not RAG). Judges against a
    reference answer when the dataset provides one, otherwise on the
    response's own merits.
    """

    ALL_METRICS = ("quality", "fluency")

    METRIC_DESCRIPTIONS = {
        "quality": (
            "LLM judge scores 0.0-1.0 for overall response quality (correctness, "
            "clarity, completeness), comparing against a reference answer when one is provided."
        ),
        "fluency": (
            "LLM judge scores 0.0-1.0 for how natural and grammatical the text reads, "
            "independent of whether it's correct."
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
        scores: dict[str, float] = {}

        if "quality" in self.metrics:
            reference_block = f"\n\nReference answer:\n{reference}" if reference else ""
            prompt = _QUALITY_PROMPT.format(
                reference_block=reference_block, input=example_input, output=output
            )
            scores["quality"] = self.judge.score(prompt)

        if "fluency" in self.metrics:
            scores["fluency"] = self.judge.score(_FLUENCY_PROMPT.format(output=output))

        return scores
