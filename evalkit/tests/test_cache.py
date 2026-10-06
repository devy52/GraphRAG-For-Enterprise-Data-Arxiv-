from __future__ import annotations

import json
import threading

from evalkit.core.cache import CachingJudgeBackend, FileCache, cache_key


def test_cache_miss_on_empty_cache(tmp_path):
    cache = FileCache(str(tmp_path / "cache"))
    assert cache.get("nonexistent-key") is None


def test_cache_set_then_get_roundtrips(tmp_path):
    cache = FileCache(str(tmp_path / "cache"))
    cache.set("key1", 0.85)
    assert cache.get("key1") == 0.85


def test_cache_entries_are_plain_readable_json_files(tmp_path):
    """Auditability requirement: a cached entry must be a plain file a
    person can open and read, not an opaque binary format."""
    cache_dir = tmp_path / "cache"
    cache = FileCache(str(cache_dir))
    cache.set("abc123", 0.5, metadata={"prompt": "was this good?", "judge_model": "gpt-4o-mini"})

    files = list(cache_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["score"] == 0.5
    assert data["prompt"] == "was this good?"
    assert "cached_at" in data


def test_cache_clear_removes_all_entries_and_reports_count(tmp_path):
    cache = FileCache(str(tmp_path / "cache"))
    cache.set("a", 0.1)
    cache.set("b", 0.2)
    cache.set("c", 0.3)

    removed = cache.clear()
    assert removed == 3
    assert cache.get("a") is None


def test_cache_clear_on_nonexistent_dir_returns_zero(tmp_path):
    cache = FileCache(str(tmp_path / "never_created"))
    assert cache.clear() == 0


def test_cache_get_handles_corrupted_entry_gracefully(tmp_path):
    """A corrupted cache file must be treated as a miss, never crash a run."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "badkey.json").write_text("not valid json{{{")

    cache = FileCache(str(cache_dir))
    assert cache.get("badkey") is None


def test_cache_key_is_deterministic():
    k1 = cache_key("LiteLLMJudge", "gpt-4o-mini", "score this: hello")
    k2 = cache_key("LiteLLMJudge", "gpt-4o-mini", "score this: hello")
    assert k1 == k2


def test_cache_key_differs_by_prompt():
    k1 = cache_key("LiteLLMJudge", "gpt-4o-mini", "prompt A")
    k2 = cache_key("LiteLLMJudge", "gpt-4o-mini", "prompt B")
    assert k1 != k2


def test_cache_key_differs_by_model():
    k1 = cache_key("LiteLLMJudge", "gpt-4o-mini", "same prompt")
    k2 = cache_key("LiteLLMJudge", "claude-haiku-4-5", "same prompt")
    assert k1 != k2


def test_cache_key_differs_by_backend():
    k1 = cache_key("LiteLLMJudge", "gpt-4o-mini", "same prompt")
    k2 = cache_key("DummyJudgeBackend", "gpt-4o-mini", "same prompt")
    assert k1 != k2


# -- CachingJudgeBackend --------------------------------------------------


class _CountingJudge:
    """Fake inner judge that counts real invocations."""

    def __init__(self):
        self.call_count = 0
        self.model = "fake-model"

    def score(self, prompt: str) -> float:
        self.call_count += 1
        return 0.42


def test_caching_judge_backend_hits_cache_on_repeat_prompt(tmp_path):
    inner = _CountingJudge()
    cache = FileCache(str(tmp_path / "cache"))
    judge = CachingJudgeBackend(inner, cache, model="fake-model")

    score1 = judge.score("the same prompt")
    score2 = judge.score("the same prompt")

    assert score1 == score2 == 0.42
    assert inner.call_count == 1  # only the first call actually hit the inner judge
    assert judge.hits == 1
    assert judge.misses == 1


def test_caching_judge_backend_misses_on_different_prompts(tmp_path):
    inner = _CountingJudge()
    cache = FileCache(str(tmp_path / "cache"))
    judge = CachingJudgeBackend(inner, cache, model="fake-model")

    judge.score("prompt one")
    judge.score("prompt two")

    assert inner.call_count == 2
    assert judge.hits == 0
    assert judge.misses == 2


def test_caching_judge_backend_persists_across_instances(tmp_path):
    """The whole point: a second Runner invocation (a new CachingJudgeBackend
    instance) against the same cache_dir must still see prior results."""
    cache_dir = str(tmp_path / "cache")

    inner1 = _CountingJudge()
    judge1 = CachingJudgeBackend(inner1, FileCache(cache_dir), model="fake-model")
    judge1.score("consistent prompt")

    inner2 = _CountingJudge()
    judge2 = CachingJudgeBackend(inner2, FileCache(cache_dir), model="fake-model")
    result = judge2.score("consistent prompt")

    assert result == 0.42
    assert inner2.call_count == 0  # never actually called — served entirely from cache


def test_caching_judge_backend_thread_safe_hit_miss_counts(tmp_path):
    """Concurrent execution calls .score() from multiple threads — hit/miss
    counters must not lose increments to a race condition."""
    inner = _CountingJudge()
    cache = FileCache(str(tmp_path / "cache"))
    judge = CachingJudgeBackend(inner, cache, model="fake-model")

    def call_unique(i: int) -> None:
        judge.score(f"unique prompt {i}")

    threads = [threading.Thread(target=call_unique, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert judge.misses == 20
    assert judge.hits == 0
