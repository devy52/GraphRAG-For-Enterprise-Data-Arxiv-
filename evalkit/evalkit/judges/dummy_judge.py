from __future__ import annotations

import hashlib

from evalkit.contracts.judge_backend import BaseJudgeBackend


class DummyJudgeBackend(BaseJudgeBackend):
    """No-API judge for tests and offline demos.

    Derives a stable pseudo-score from the prompt text via a hash — it is
    NOT a real quality signal. Its only job is letting the pipeline (config
    -> dataset -> adapter -> evaluator -> report) run and be tested without
    API calls or cost. Use ``litellm`` for real scoring.
    """

    def __init__(self, model: str = "dummy", **kwargs) -> None:
        self.model = model

    def score(self, prompt: str) -> float:
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        return (int(digest[:8], 16) % 1000) / 1000
