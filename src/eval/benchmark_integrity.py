"""Integrity checks for the authoritative Evaluation V2 dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_v2_dataset(dataset_path: Path, corpus_chunks_path: Path) -> Dict[str, Any]:
    questions: List[Dict[str, Any]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {dataset_path}:{line_no}: {exc}") from exc

    if len(questions) != 50:
        raise ValueError(f"Expected exactly 50 benchmark questions; found {len(questions)}")

    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark question IDs must be unique")

    answerable = [q for q in questions if q.get("answerable") is True]
    unanswerable = [q for q in questions if q.get("answerable") is False]
    if len(answerable) != 40 or len(unanswerable) != 10:
        raise ValueError(
            f"Expected 40 answerable + 10 unanswerable questions; found {len(answerable)} + {len(unanswerable)}"
        )

    for q in answerable:
        if not q.get("required_facts"):
            raise ValueError(f"Answerable question {q['id']} has no required_facts")
        gold_chunks = q.get("gold_chunk_ids", [])
        gold_evidence = q.get("gold_evidence", [])
        if not gold_chunks and not gold_evidence:
            raise ValueError(f"Answerable question {q['id']} has no gold_chunk_ids or gold_evidence")
        if q.get("hop_type") == "out-of-scope":
            raise ValueError(f"Answerable question {q['id']} is incorrectly marked out-of-scope")

    for q in unanswerable:
        if q.get("hop_type") != "out-of-scope":
            raise ValueError(f"Unanswerable question {q['id']} must use hop_type=out-of-scope")
        if q.get("gold_chunk_ids") or q.get("gold_evidence"):
            raise ValueError(f"Unanswerable question {q['id']} must not have gold retrieval evidence")

    with open(corpus_chunks_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)
    corpus_ids = {row["chunk_id"] for row in corpus}
    missing = [
        (q["id"], cid)
        for q in answerable
        for cid in q.get("gold_chunk_ids", [])
        if cid not in corpus_ids
    ]
    if missing:
        preview = ", ".join(f"{qid}:{cid}" for qid, cid in missing[:10])
        raise ValueError(f"Gold chunk IDs missing from corpus ({len(missing)}): {preview}")

    return {
        "questions": len(questions),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "gold_chunk_references": sum(len(q.get("gold_chunk_ids", [])) for q in answerable),
        "dataset_sha256": sha256_file(dataset_path),
        "corpus_chunks_sha256": sha256_file(corpus_chunks_path),
    }
