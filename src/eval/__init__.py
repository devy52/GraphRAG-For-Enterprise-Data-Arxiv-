"""Evaluation and benchmarking package.

Heavy runtime components are imported lazily so deterministic evaluators can be
unit-tested without requiring the LLM/vector/graph runtime dependencies.
"""

from src.eval.dataset import (
    BenchmarkDataset,
    EvalHopType,
    EvalQuestion,
    get_canonical_evaluation_dataset,
)

__all__ = [
    "BenchmarkDataset",
    "EvalHopType",
    "EvalQuestion",
    "get_canonical_evaluation_dataset",
    "BenchmarkRunner",
    "BenchmarkReporter",
    "EvalMetricRecord",
    "ComparativeBenchmarkResult",
]


def __getattr__(name):
    if name in {"BenchmarkRunner", "ComparativeBenchmarkResult", "EvalMetricRecord"}:
        from src.eval.runner import BenchmarkRunner, ComparativeBenchmarkResult, EvalMetricRecord
        return {
            "BenchmarkRunner": BenchmarkRunner,
            "ComparativeBenchmarkResult": ComparativeBenchmarkResult,
            "EvalMetricRecord": EvalMetricRecord,
        }[name]
    if name == "BenchmarkReporter":
        from src.eval.report import BenchmarkReporter
        return BenchmarkReporter
    raise AttributeError(name)
