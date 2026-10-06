from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseEvaluator(ABC):
    """Contract for an evaluator module (one per track: RAG, codegen,
    summarization, agentic, or your own custom track).

    Implement exactly one method. The runner instantiates your evaluator as
    ``YourEvaluator(judge=<judge_backend>, metrics=<list[str] | None>)`` —
    keep your constructor accepting those two keyword arguments (or **kwargs)
    so it works from config alone.

    This contract is frozen at 1.0: new optional parameters may be added to
    ``evaluate`` in the future, but the required arguments below will not
    change shape. A custom evaluator you write today will keep working.
    """

    #: Optional: {metric_name: human-readable description of how it's
    #: computed}. Purely additive — leave empty and reports just won't
    #: show a methodology blurb for your metrics. Not required.
    METRIC_DESCRIPTIONS: dict[str, str] = {}

    @abstractmethod
    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        """Score one example.

        Args:
            example_input: the input given to the system under test.
            output: what the system under test produced.
            reference: an optional ground-truth answer, if the dataset has one.
            context: optional retrieved passages (e.g. for RAG).
            metadata: any extra per-example fields from the dataset.

        Returns:
            A dict of ``{metric_name: score}`` for whichever metrics this
            evaluator computes. Only include metrics you actually scored.
        """
        raise NotImplementedError
