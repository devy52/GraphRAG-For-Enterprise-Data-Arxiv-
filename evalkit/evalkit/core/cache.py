from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Optional

from evalkit.contracts.judge_backend import BaseJudgeBackend


class FileCache:
    """Simple, inspectable file-based cache — one JSON file per entry under
    a cache directory. No database, no server: every cached score is a
    plain file you can open, read, and delete by hand if you want to.
    """

    def __init__(self, cache_dir: str = ".evalkit/cache") -> None:
        self.cache_dir = Path(cache_dir)

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[float]:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return float(data["score"])
        except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
            return None  # corrupted or unreadable entry — treat as a miss, never crash a run over it

    def set(self, key: str, score: float, metadata: Optional[dict] = None) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(key)
        payload = {"score": score, "cached_at": time.time(), **(metadata or {})}
        path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> int:
        if not self.cache_dir.exists():
            return 0
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count


def cache_key(judge_backend_name: str, judge_model: str, prompt: str) -> str:
    """The prompt already fully encodes the evaluator's template plus the
    example's input/output/context — so (backend, model, prompt) is a
    complete, sufficient cache key without needing to separately hash
    evaluator version, example fields, etc."""
    canonical = f"{judge_backend_name}|{judge_model}|{prompt}"
    return hashlib.sha256(canonical.encode()).hexdigest()


class CachingJudgeBackend(BaseJudgeBackend):
    """Wraps any BaseJudgeBackend with a transparent cache: same backend,
    same model, same prompt -> same score, no repeat API call. Tracks
    hits/misses on the instance so a run can report cache effectiveness.

    Note: this only helps judge-backend-based evaluators (rag, generic).
    The ragas track manages its own LLM calls internally, bypassing
    judge_backend entirely, so caching doesn't apply there.
    """

    def __init__(self, inner: BaseJudgeBackend, cache: FileCache, model: str = "") -> None:
        self.inner = inner
        self.cache = cache
        self.model = model or getattr(inner, "model", "")
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()  # hits/misses may be incremented from multiple worker threads

    def score(self, prompt: str) -> float:
        key = cache_key(type(self.inner).__name__, self.model, prompt)
        cached = self.cache.get(key)
        if cached is not None:
            with self._lock:
                self.hits += 1
            return cached

        with self._lock:
            self.misses += 1
        result = self.inner.score(prompt)
        self.cache.set(
            key,
            result,
            metadata={
                "judge_backend": type(self.inner).__name__,
                "judge_model": self.model,
                "prompt": prompt,
            },
        )
        return result
