from __future__ import annotations

import json
import math
import re
from typing import Any

from evalkit.contracts.judge_backend import BaseJudgeBackend


class LiteLLMJudge(BaseJudgeBackend):
    """Default provider-agnostic LLM judge.

    The preferred response contract is strict JSON::

        {"score": 0.85, "reasoning": "..."}

    LiteLLM is asked for JSON-object output first. Providers/models that reject
    ``response_format`` get one compatibility retry without that option. The
    fallback parser accepts an actual JSON score, a labeled score, or a bare
    numeric response; ambiguous free-form text is rejected instead of taking
    the first number it happens to contain.
    """

    _SCORE_PATTERN = re.compile(
        r'(?i)["\']?score["\']?\s*(?:is\s*)?[:=]?\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\b'
    )
    _BARE_NUMBER_PATTERN = re.compile(
        r"^-?(?:\d+(?:\.\d*)?|\.\d+)$"
    )

    def __init__(self, model: str = "gpt-4o-mini", **litellm_kwargs) -> None:
        self.model = model
        self.litellm_kwargs = litellm_kwargs
        if "api_base" not in self.litellm_kwargs or "api_key" not in self.litellm_kwargs:
            try:
                import os
                from src.core.config import get_settings

                settings = get_settings()
                if "fireworks" in self.model.lower():
                    fw_key = os.getenv("FIREWORKS_API_KEY")
                    if fw_key and "api_key" not in self.litellm_kwargs:
                        self.litellm_kwargs["api_key"] = fw_key
                else:
                    if "api_base" not in self.litellm_kwargs and getattr(settings, "llm_base_url", None):
                        self.litellm_kwargs["api_base"] = settings.llm_base_url
                    if "api_key" not in self.litellm_kwargs and getattr(settings, "llm_api_key", None):
                        self.litellm_kwargs["api_key"] = settings.llm_api_key
            except Exception:
                pass

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

        import time

        kwargs = dict(self.litellm_kwargs)
        kwargs.setdefault("timeout", 45)
        kwargs.setdefault("max_tokens", 3000)
        explicit_response_format = kwargs.pop("response_format", None)
        response_format = explicit_response_format or {"type": "json_object"}
        last_exc: Exception | None = None

        for attempt in range(3):
            cur_kwargs = dict(kwargs)
            if attempt > 0:
                cur_kwargs["max_tokens"] = cur_kwargs.get("max_tokens", 3000) + 1500
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    response_format=response_format,
                    **cur_kwargs,
                )
                text = self._extract_content(response)
                return self._parse_score(text)
            except Exception as exc:
                if explicit_response_format is None and self._is_response_format_error(exc):
                    try:
                        response = litellm.completion(
                            model=self.model,
                            messages=messages,
                            **cur_kwargs,
                        )
                        text = self._extract_content(response)
                        return self._parse_score(text)
                    except Exception as inner_exc:
                        exc = inner_exc
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0 * (2 ** attempt))

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("LiteLLM completion failed with no response")

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

