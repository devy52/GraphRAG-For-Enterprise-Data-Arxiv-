from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class EvalExample(BaseModel):
    """One row of an evalkit dataset (JSONL, one JSON object per line).

    - id: optional unique identifier (generated deterministically if omitted).
    - input: required, what's given to the system under test.
    - reference: optional ground-truth answer.
    - context: optional list of retrieved passages (for RAG tracks).
    - metadata: anything else — e.g. {"precomputed_output": "..."} for the
      built-in StaticAdapter, when you already have outputs to score.
    """

    id: Optional[str] = None
    input: str
    reference: Optional[str] = None
    context: Optional[list[str]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "input" not in data and "question" in data:
                data["input"] = data.pop("question")
            if "reference" not in data and "reference_answer" in data:
                data["reference"] = data.pop("reference_answer")
            known_keys = {"id", "input", "reference", "context", "metadata"}
            extras = {k: v for k, v in data.items() if k not in known_keys}
            if extras:
                meta = dict(data.get("metadata", {}))
                meta.update(extras)
                data["metadata"] = meta
                for k in extras:
                    del data[k]
        return data

    @model_validator(mode="after")
    def _fill_id(self) -> "EvalExample":
        if self.id is None:
            canonical = json.dumps(
                {"input": self.input, "metadata": self.metadata}, sort_keys=True
            )
            self.id = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return self


def load_dataset(path: str) -> list[EvalExample]:
    examples: list[EvalExample] = []
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON — {exc}") from exc
            examples.append(EvalExample(**raw))
    if not examples:
        raise ValueError(f"{path} contained no examples")
    return examples
