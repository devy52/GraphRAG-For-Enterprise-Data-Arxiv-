from __future__ import annotations

from typing import Any, Optional

from evalkit.contracts.adapter import BaseAdapter


class StaticAdapter(BaseAdapter):
    """Adapter for datasets where the output was already generated offline —
    you just want to score existing (input, output) pairs. Every example's
    metadata must include a "precomputed_output" key.

    For a live system, write your own adapter instead: it's the one part of
    evalkit meant to live in your project, not this package.
    """

    def run(self, example_input: str, metadata: Optional[dict[str, Any]] = None) -> str:
        if not metadata or "precomputed_output" not in metadata:
            raise ValueError(
                "StaticAdapter requires metadata['precomputed_output'] on every "
                "example. Use your own BaseAdapter subclass to call a live system."
            )
        return metadata["precomputed_output"]
