"""
Evalkit Dataset Exporter Script.

Architecture Role:
    Testing & Evaluation Integration. Converts the internal 50-question stratified
    benchmark dataset from `src.eval.dataset` into the standard JSONL format
    consumed by `evalkit`.

Inputs:
    - Canonical benchmark dataset from `src.eval.dataset.get_canonical_evaluation_dataset()`.

Outputs:
    - `data/evalkit_dataset.jsonl`: JSON Lines dataset where each record adheres to
      `evalkit.core.dataset.EvalExample` (`input`, `reference`, `context`, `metadata`).

Design Decisions:
    - Reference Synthesis: For standard questions, synthesizes reference statements from
      expected entities and keywords; for out-of-scope questions, provides standard
      refusal reference text.
    - Zero Modification to Core: Lives outside `src/` to ensure core engine remains
      independent of external evaluation frameworks.
"""

from pathlib import Path
import json
import sys

# Ensure repository root is in python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.eval.dataset import EvalHopType, get_canonical_evaluation_dataset


def export_dataset(output_path: Path) -> int:
    """
    Exports canonical benchmark dataset to an evalkit-compliant JSONL file.

    Args:
        output_path: Target path for the JSONL file.

    Returns:
        Number of exported examples.
    """
    dataset = get_canonical_evaluation_dataset()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for q in dataset.questions:
            # Construct a clear reference based on question characteristics
            if q.should_refuse:
                reference = "I do not have sufficient evidence in the retrieved corpus to answer this question."
            else:
                reference = f"Key entities: {', '.join(q.target_entities)}. Expected facts: {', '.join(q.expected_answer_keywords)}."

            row = {
                "input": q.question,
                "reference": reference,
                "context": None,  # Context will be supplied dynamically at runtime by GraphRAGAdapter
                "metadata": {
                    "id": q.id,
                    "hop_type": q.hop_type.value,
                    "should_refuse": q.should_refuse,
                    "target_entities": q.target_entities,
                    "expected_keywords": q.expected_answer_keywords,
                },
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    return count


if __name__ == "__main__":
    out_file = repo_root / "data" / "evalkit_dataset.jsonl"
    total = export_dataset(out_file)
    print(f"Exported {total} canonical benchmark questions to {out_file}")
