"""Validate Evaluation V2 ground truth before any benchmark run."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.benchmark_integrity import validate_v2_dataset

DATASET = ROOT / "data" / "benchmark_v2_dataset.jsonl"
CORPUS = ROOT / "data" / "corpus" / "chunks.json"


def main() -> None:
    result = validate_v2_dataset(DATASET, CORPUS)
    print("Evaluation V2 dataset validation: PASS")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
