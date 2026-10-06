from __future__ import annotations

from abc import ABC, abstractmethod


class BaseJudgeBackend(ABC):
    """Contract for LLM-judge scoring backends.

    The built-in ``LiteLLMJudge`` covers switching providers (OpenAI,
    Anthropic, OpenRouter, Fireworks, local vLLM, ...) via a plain model
    string. Implement this contract instead if you want to change the
    judging *logic* itself — e.g. a self-hosted classifier, an ensemble of
    judges, or a non-LLM heuristic.
    """

    @abstractmethod
    def score(self, prompt: str) -> float:
        """Send a judge prompt and return a numeric score.

        Implementations decide how to parse the response into a float
        (e.g. a 0-1 or 1-5 scale) — evaluators that use this backend write
        their prompts expecting whichever scale the backend documents.
        """
        raise NotImplementedError
