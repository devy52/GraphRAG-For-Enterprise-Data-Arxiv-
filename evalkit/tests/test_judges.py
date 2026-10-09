from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from evalkit.judges.dummy_judge import DummyJudgeBackend
from evalkit.judges.litellm_judge import LiteLLMJudge


def test_dummy_judge_is_deterministic():
    judge = DummyJudgeBackend()
    assert judge.score("same prompt") == judge.score("same prompt")


def test_dummy_judge_varies_by_prompt():
    judge = DummyJudgeBackend()
    assert judge.score("prompt a") != judge.score("prompt b")


def test_dummy_judge_score_in_range():
    judge = DummyJudgeBackend()
    for prompt in ["a", "b", "some longer prompt text", ""]:
        score = judge.score(prompt)
        assert 0.0 <= score < 1.0


@pytest.mark.parametrize(
    "response_text,expected",
    [
        ('{"score": 0.85, "reasoning": "All key facts match."}', 0.85),
        ('{"score": 0.75, "reasoning": "Covers 3 of 4 claims."}', 0.75),
        ("Score: 0.4", 0.4),
        ("0.85", 0.85),
        ("```json\n{\"score\": 1.0, \"reasoning\": \"complete\"}\n```", 1.0),
        ("The score is 0.72 out of 1.0.", 0.72),
    ],
)
def test_parse_score_handles_structured_and_unambiguous_fallbacks(response_text, expected):
    assert LiteLLMJudge._parse_score(response_text) == expected


def test_parse_score_rejects_regex_collision():
    with pytest.raises(ValueError, match="could not be parsed unambiguously"):
        LiteLLMJudge._parse_score("The answer covers 3 out of 4 claims and is fairly strong.")


@pytest.mark.parametrize("response_text", ["-0.5", "1.01", "NaN", "inf"])
def test_parse_score_rejects_out_of_range_or_non_finite(response_text):
    with pytest.raises(ValueError):
        LiteLLMJudge._parse_score(response_text)


@pytest.mark.parametrize(
    "response_text",
    [
        "I cannot provide a numeric score for this.",
        "",
        "excellent, great job!",
        '{"reasoning": "missing score"}',
        '{"score": "0.8", "reasoning": "string"}',
    ],
)
def test_parse_score_raises_on_invalid_response(response_text):
    with pytest.raises(ValueError):
        LiteLLMJudge._parse_score(response_text)


def test_litellm_judge_requests_structured_json():
    fake_response = {
        "choices": [
            {"message": {"content": '{"score": 0.9, "reasoning": "Good."}'}}
        ]
    }
    fake_litellm = SimpleNamespace(completion=lambda **kwargs: fake_response)
    with patch.dict("sys.modules", {"litellm": fake_litellm}):
        with patch.object(fake_litellm, "completion", wraps=fake_litellm.completion) as mock_completion:
            judge = LiteLLMJudge(model="gpt-4o-mini")
            score = judge.score("Is this good?")

    assert score == 0.9
    _, kwargs = mock_completion.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "Is this good?" in kwargs["messages"][0]["content"]
    assert '"score"' in kwargs["messages"][0]["content"]


def test_litellm_judge_falls_back_when_provider_rejects_response_format():
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        if "response_format" in kwargs:
            raise RuntimeError("unsupported response_format")
        return {"choices": [{"message": {"content": "Score: 0.8"}}]}

    with patch.dict("sys.modules", {"litellm": SimpleNamespace(completion=completion)}):
        score = LiteLLMJudge(model="local-model").score("prompt")

    assert score == 0.8
    assert len(calls) == 2
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


def test_litellm_judge_passes_through_extra_kwargs():
    fake_response = {"choices": [{"message": {"content": '{"score": 0.5}'}}]}
    fake_litellm = SimpleNamespace(completion=lambda **kwargs: fake_response)
    with patch.dict("sys.modules", {"litellm": fake_litellm}):
        with patch.object(fake_litellm, "completion", wraps=fake_litellm.completion) as mock_completion:
            judge = LiteLLMJudge(model="gpt-4o-mini", temperature=0.0, max_tokens=10)
            judge.score("prompt")

    _, kwargs = mock_completion.call_args
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 10


def test_explicit_response_format_is_respected():
    fake_response = {"choices": [{"message": {"content": '{"score": 0.5}'}}]}
    fake_litellm = SimpleNamespace(completion=lambda **kwargs: fake_response)
    with patch.dict("sys.modules", {"litellm": fake_litellm}):
        with patch.object(fake_litellm, "completion", wraps=fake_litellm.completion) as mock_completion:
            LiteLLMJudge(model="gpt-4o-mini", response_format={"type": "json_schema"}).score("prompt")

    _, kwargs = mock_completion.call_args
    assert kwargs["response_format"] == {"type": "json_schema"}


def test_litellm_judge_retries_transient_failures_and_succeeds():
    class Timeout(Exception):
        pass

    calls = 0

    def completion(**kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise Timeout("Request timed out")
        return {"choices": [{"message": {"content": '{"score": 0.95, "reasoning": "ok"}'}}]}

    fake_litellm = SimpleNamespace(
        completion=completion,
        exceptions=SimpleNamespace(Timeout=Timeout),
    )
    with patch.dict("sys.modules", {"litellm": fake_litellm}):
        judge = LiteLLMJudge(model="gpt-4o-mini", max_retries=3, retry_base_delay=0.001)
        score = judge.score("prompt")

    assert score == 0.95
    assert calls == 3


def test_litellm_judge_cache_fingerprint():
    judge = LiteLLMJudge(model="gpt-4o-mini", temperature=0.7)
    assert judge.cache_fingerprint == {"temperature": 0.7}

