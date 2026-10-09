from __future__ import annotations

import json
import math
import random
import re
import time
from typing import Any

from evalkit.contracts.judge_backend import BaseJudgeBackend

# Retryable = transient, worth waiting and trying again. NOT retryable =
# permanent (auth, bad request, content policy, schema) — retrying these
# just wastes time and money on a call that will never succeed. Resolved
# lazily against litellm.exceptions in score(), not imported at module
# level, so importing this module doesn't require litellm to be installed
# unless it's actually used.
_RETRYABLE_EXCEPTION_NAMES = (
    "RateLimitError",
    "Timeout",
    "APIConnectionError",
    "ServiceUnavailableError",
    "InternalServerError",
    "BadGatewayError",
)


class LiteLLMJudge(BaseJudgeBackend):
    """Default provider-agnostic LLM judge.

    The preferred response contract is strict JSON::

        {"score": 0.85, "reasoning": "..."}

    LiteLLM is asked for JSON-object output first. Providers/models that
    reject ``response_format`` get one compatibility retry without that
    option, within the same attempt — this is a format negotiation, not a
    transient failure, so it doesn't consume a retry slot. The parser
    accepts an actual JSON score, a labeled score, or a bare numeric
    response; ambiguous free-form text is rejected instead of taking the
    first number it happens to contain.

    Separately, transient failures (rate limits, timeouts, connection
    errors, 5xx) are retried with exponential backoff and jitter, up to
    `max_retries` times. Permanent failures (auth, bad request, content
    policy) are never retried — retrying those just delays an inevitable
    failure. Configurable via judge_config in your YAML:
    `judge_config: {max_retries: 5, retry_base_delay: 2.0}`.

    Credentials are read the normal LiteLLM way (env vars like
    OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) — evalharness never touches
    them directly, and never reaches into application-specific settings
    objects to source them.
    """

    _SCORE_PATTERN = re.compile(
        r'(?i)["\']?score["\']?\s*(?:is\s*)?[:=]?\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\b'
    )
    _BARE_NUMBER_PATTERN = re.compile(r"^-?(?:\d+(?:\.\d*)?|\.\d+)$")

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        **litellm_kwargs,
    ) -> None:
        self.model = model
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.litellm_kwargs = litellm_kwargs

    @property
    def cache_fingerprint(self) -> dict:
        return self.litellm_kwargs

    def score(self, prompt: str) -> float:
        import litellm

        messages = [
            {
                "role": "user",
                "content": (
                    f"{prompt.rstrip()}\n\n"
                    "Return ONLY a JSON object with this exact shape:\n"
                    '{"score": <number between 0.0 and 1.0>, "reasoning": "<brief explanation>"}\n'
                    "The score must be a float between 0.0 (worst) and 1.0 (best)."
                ),
            }
        ]

        kwargs = dict(self.litellm_kwargs)
        kwargs.setdefault("timeout", 45)
        kwargs.setdefault("max_tokens", 3000)
        explicit_response_format = kwargs.pop("response_format", None)
        response_format = explicit_response_format or {"type": "json_object"}

        exceptions_module = getattr(litellm, "exceptions", None)
        retryable_exceptions = tuple(
            getattr(exceptions_module, name)
            for name in _RETRYABLE_EXCEPTION_NAMES
            if exceptions_module is not None and hasattr(exceptions_module, name)
        )

        attempt = 0
        while True:
            try:
                text = self._attempt_completion(messages, kwargs, response_format, explicit_response_format)
                return self._parse_score(text)
            except retryable_exceptions:
                if attempt >= self.max_retries:
                    raise
                delay = self.retry_base_delay * (2**attempt) + random.uniform(0, self.retry_base_delay)
                time.sleep(delay)
                attempt += 1

    def _attempt_completion(
        self, messages: list[dict], kwargs: dict, response_format: dict, explicit_response_format: Any
    ) -> str:
        """One logical attempt: try with response_format, and if the
        provider rejects that specific option, retry once without it in
        the same attempt (a format negotiation, not a transient failure —
        doesn't consume an outer retry slot)."""
        import litellm

        try:
            response = litellm.completion(
                model=self.model, messages=messages, response_format=response_format, **kwargs
            )
            return self._extract_content(response)
        except Exception as exc:
            if explicit_response_format is None and self._is_response_format_error(exc):
                response = litellm.completion(model=self.model, messages=messages, **kwargs)
                return self._extract_content(response)
            raise

    @classmethod
    def _extract_content(cls, response: Any) -> str:
        try:
            msg = response["choices"][0]["message"]
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Judge response did not contain message content: {response!r}") from exc

        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            # Some OpenAI-compatible APIs return structured content parts.
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts).strip()

        # Fallback to reasoning_content if thinking tokens consumed the response
        reasoning = msg.get("reasoning_content") if isinstance(msg, dict) else getattr(msg, "reasoning_content", None)
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()

        raise ValueError(f"Judge response content was empty: {response!r}")

    @classmethod
    def _parse_score(cls, text: str) -> float:
        raw = text.strip()
        if not raw:
            raise ValueError("Judge model response was empty; expected JSON with a numeric 'score'.")

        # Preferred path: strict JSON object.
        try:
            payload = json.loads(cls._strip_code_fence(raw))
        except json.JSONDecodeError:
            payload = None

        if payload is not None:
            if isinstance(payload, dict):
                if "score" not in payload:
                    raise ValueError(
                        f"Judge JSON response must be an object containing numeric 'score': {text!r}"
                    )
                score = payload["score"]
                if isinstance(score, bool) or not isinstance(score, (int, float)):
                    raise ValueError(f"Judge JSON 'score' must be numeric: {text!r}")
                return cls._validate_score(float(score), source="JSON")
            # JSON numbers are valid legacy bare-score responses.
            if isinstance(payload, (int, float)) and not isinstance(payload, bool):
                return cls._validate_score(float(payload), source="bare numeric JSON")
            raise ValueError(
                f"Judge JSON response must be an object containing numeric 'score': {text!r}"
            )

        # Provider fallback: allow an explicitly labeled score.
        labeled = cls._SCORE_PATTERN.search(raw)
        if labeled:
            return cls._validate_score(float(labeled.group(1)), source="labeled text")

        # And a bare number for legacy/custom judges that still return one.
        if cls._BARE_NUMBER_PATTERN.fullmatch(raw):
            return cls._validate_score(float(raw), source="bare numeric text")

        raise ValueError(
            "Judge model response could not be parsed unambiguously. Expected JSON "
            '{"score": <0..1>, "reasoning": "..."}, a labeled `score: 0.85`, '
            f"or a bare number; got: {text!r}"
        )

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return text

    @staticmethod
    def _validate_score(score: float, *, source: str) -> float:
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(
                f"Judge {source} score must be finite and between 0.0 and 1.0; got {score!r}"
            )
        return score

    @staticmethod
    def _is_response_format_error(exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "response_format",
            "json_object",
            "structured output",
            "unsupported parameter",
            "invalid parameter",
        )
        return any(marker in message for marker in markers)
