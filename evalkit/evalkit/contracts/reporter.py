from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseReporter(ABC):
    """Contract for report renderers. Built-ins are markdown (default), html,
    and json; implement this to push results to your own dashboard, Slack,
    etc.
    """

    @abstractmethod
    def render(
        self,
        results: list[dict[str, Any]],
        output_path: str,
        run_info: Optional[dict[str, Any]] = None,
    ) -> None:
        """Write a report for the given per-example results to output_path.

        run_info is optional metadata (track, dataset, judge backend/model,
        thresholds, per-metric descriptions) for reporters that want to
        explain methodology, not just list scores. Safe to ignore.
        """
        raise NotImplementedError
