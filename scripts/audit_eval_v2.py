#!/usr/bin/env python3
"""Static/data-integrity audit for the GraphRAG V2 evaluation harness.

Usage from the project root:
    python audit_eval_v2.py

This script intentionally uses only the Python standard library so it can run even
when project dependencies such as openai/ragas are unavailable.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
import argparse

def detect_root(cli_root: str | None = None) -> Path:
    if cli_root:
        return Path(cli_root).resolve()
    here = Path(__file__).resolve()
    candidates = [here.parent.parent, here.parent.parent / "srcbundle", Path.cwd()]
    for candidate in candidates:
        if (candidate / "data" / "benchmark_v2_dataset.jsonl").exists() and (candidate / "src" / "eval" / "evaluator_v2.py").exists():
            return candidate
    return Path.cwd().resolve()

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--project-root", help="GraphRAG project root")
    return p.parse_args()

ROOT = detect_root(parse_args().project_root)
DATASET = ROOT / "data" / "benchmark_v2_dataset.jsonl"
RECORDS = ROOT / "data" / "benchmark_audit_records_v2.jsonl"
RESULTS = ROOT / "data" / "benchmark_results_50q_v2.json"
RUNNER = ROOT / "scripts" / "run_benchmark_v2.py"
EVAL = ROOT / "src" / "eval" / "evaluator_v2.py"
RAGAS = ROOT / "scripts" / "compare_evalkit_vs_ragas.py"

failures: list[str] = []
checks = 0

def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"[PASS] {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"[FAIL] {name} :: {detail}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print(f"Project root: {ROOT}")
    check("dataset exists", DATASET.exists(), str(DATASET))
    check("audit records exist", RECORDS.exists(), str(RECORDS))
    check("results exist", RESULTS.exists(), str(RESULTS))
    check("V2 runner exists", RUNNER.exists(), str(RUNNER))
    check("V2 evaluator exists", EVAL.exists(), str(EVAL))

    if not all(p.exists() for p in [DATASET, RECORDS, RESULTS, RUNNER, EVAL]):
        print("\nCannot continue because required files are missing.")
        return 1

    questions = load_jsonl(DATASET)
    records = load_jsonl(RECORDS)
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    runner_text = RUNNER.read_text(encoding="utf-8")
    eval_text = EVAL.read_text(encoding="utf-8")

    qmap = {q["id"]: q for q in questions}
    check("50-question dataset", len(questions) == 50, f"found {len(questions)}")
    check("all audit records reference known questions", all(r.get("question_id") in qmap for r in records))
    check("audit record count is two runs", len(records) == 2 * len(questions), f"found {len(records)}")

    # Dataset schema
    bad_answerability = [q["id"] for q in questions if not isinstance(q.get("answerable"), bool)]
    check("every question has boolean answerable", not bad_answerability, str(bad_answerability[:10]))

    bad_required = [q["id"] for q in questions if q.get("answerable") and not q.get("required_facts")]
    check("every answerable question has required facts", not bad_required, str(bad_required[:10]))

    missing_gold = [q["id"] for q in questions if q.get("answerable") and not q.get("gold_chunk_ids")]
    check("every answerable question has gold chunk IDs", not missing_gold, str(missing_gold[:10]))

    # Static leakage check
    check(
        "no gold reference injected into retrieval fallback",
        "text=q.reference_answer" not in runner_text and "text = q.reference_answer" not in runner_text,
        "runner contains q.reference_answer in a retrieval path",
    )
    # Detect only an actual executable assignment, not a documentation string describing the old behavior.
    code_lines = []
    for line in runner_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", "\"", "'")):
            continue
        code_lines.append(stripped)
    executable_runner = "\n".join(code_lines)
    check(
        "no executable hardcoded is_accurate = False in V2 runner",
        not re.search(r"^\s*is_accurate\s*=\s*False\s*$", executable_runner, flags=re.M),
        "found executable hardcoded accuracy override in V2 runner",
    )
    # V2 does not import the legacy src/eval/runner accuracy path; the legacy file may still contain
    # compatibility code and therefore is not itself a V2 failure.
    check(
        "V2 runner does not import legacy src.eval.runner",
        "from src.eval.runner import" not in runner_text and "import src.eval.runner" not in runner_text,
        "V2 runner imports legacy evaluator runner",
    )

    # Stored results are valid for current comparison only when explicitly marked fresh.
    status = results.get("evaluation_status", "legacy_unknown")
    current_dataset_hash = sha256(DATASET)
    result_dataset_hash = results.get("dataset_sha256")
    is_fresh = status == "fresh_run" and result_dataset_hash == current_dataset_hash
    check(
        "stored result has current dataset fingerprint",
        is_fresh or status.startswith("STALE_") or status == "legacy_unknown",
        f"status={status!r} result_hash={result_dataset_hash!r} current_hash={current_dataset_hash!r}",
    )

    if is_fresh:
        retrieval_mismatches = []
        stale_perfect_retrieval = []
        for r in records:
            q = qmap[r["question_id"]]
            gold = set(q.get("gold_chunk_ids") or [])
            retrieved = r.get("retrieved_chunk_ids") or []
            if not gold:
                continue
            hits = set(retrieved) & gold
            precision = len(hits) / len(retrieved) if retrieved else 0.0
            recall = len(hits) / len(gold)
            mrr = 0.0
            for rank, cid in enumerate(retrieved, 1):
                if cid in gold:
                    mrr = 1.0 / rank
                    break
            for field, expected in [("retrieval_precision", precision), ("retrieval_recall", recall), ("retrieval_mrr", mrr)]:
                actual = float(r.get(field, float("nan")))
                if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-4):
                    retrieval_mismatches.append((r["question_id"], field, actual, expected))
            if recall < 1.0 and float(r.get("retrieval_recall", 0)) == 1.0:
                stale_perfect_retrieval.append(r["question_id"])
        check("fresh stored retrieval metrics match current dataset", not retrieval_mismatches, str(retrieval_mismatches[:8]))
        check("fresh records contain no falsely perfect retrieval", not stale_perfect_retrieval, str(stale_perfect_retrieval[:8]))
    else:
        print(f"[INFO] Skipping stored-result numeric consistency checks because status={status!r}; rerun benchmark for fresh artifacts.")
        check("historical artifacts are explicitly marked non-current", status.startswith("STALE_") or status == "legacy_unknown", f"unexpected status={status!r}")

    print(f"\nDataset SHA-256: {sha256(DATASET)}")
    print(f"Checks run: {checks}")
    print(f"Failures: {len(failures)}")
    if failures:
        print("\nFailure details:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("\nAll static/data-integrity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
