from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

try:
    from evalkit.contracts.adapter import AdapterResponse, BaseAdapter
except ImportError:
    @dataclass
    class AdapterResponse:
        """Structured result returned by a system-under-test adapter."""

        output: str
        context: Optional[list[str]] = None
        latency_ms: Optional[float] = None
        metadata: Optional[dict[str, Any]] = None

    class BaseAdapter(ABC):
        """Contract for wrapping the system under test."""

        @abstractmethod
        def run(
            self, example_input: str, metadata: Optional[dict[str, Any]] = None
        ) -> str | AdapterResponse:
            raise NotImplementedError

