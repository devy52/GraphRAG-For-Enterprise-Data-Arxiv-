from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from evalkit.core.runner import EvalResult


def generate_run_id() -> str:
    """Timestamp + short random suffix — sorts naturally by time, stays
    unique even if two runs start in the same second."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}-{suffix}"


class RunStore:
    """Persists full run results as plain JSON files — one per run, human
    readable, no database. This is what makes `evalkit diff` possible
    without needing the old config or system still available to re-run:
    compare against history instead of re-executing it.
    """

    def __init__(self, runs_dir: str = ".evalkit/runs") -> None:
        self.runs_dir = Path(runs_dir)

    def save(self, result: EvalResult, run_id: Optional[str] = None) -> str:
        run_id = run_id or generate_run_id()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{run_id}.json"

        payload = {
            "run_id": run_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "track": result.config.track,
            "dataset": result.config.dataset,
            "adapter": result.config.adapter,
            "judge_backend": result.config.judge_backend,
            "judge_model": result.config.judge_model,
            "aggregate": result.aggregate(),
            "cache_stats": result.cache_stats,
            "per_example": result.per_example,
        }
        path.write_text(json.dumps(payload, indent=2))
        return run_id

    def load(self, run_id: str) -> dict[str, Any]:
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            available = self.list_runs()
            hint = f"Available runs: {', '.join(available)}" if available else "No runs stored yet."
            raise FileNotFoundError(f"No stored run '{run_id}' in {self.runs_dir}. {hint}")
        return json.loads(path.read_text())

    def list_runs(self) -> list[str]:
        if not self.runs_dir.exists():
            return []
        return sorted(p.stem for p in self.runs_dir.glob("*.json"))
