#!/usr/bin/env python3
"""Fresh stratified Plain Vector vs Hybrid GraphRAG comparison.

This runner reuses the authoritative V2 question set but only evaluates a small
stratified sample. It executes each question through both systems and writes raw
per-question evidence plus aggregate comparisons. It never injects reference
aanswers into retrieval or synthesis.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_scripts_dir = Path(__file__).resolve().parent
_repo_root = _scripts_dir.parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from run_benchmark_v2 import BenchmarkV2Runner, load_v2_questions, validate_v2_dataset, DATASET_FILE, REPO_ROOT


def select(rows: List[Any], per_hop: int) -> List[Any]:
    order = ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]
    groups: Dict[str, List[Any]] = {}
    for row in rows:
        groups.setdefault(row.hop_type, []).append(row)
    out: List[Any] = []
    for hop in order:
        out.extend(groups.get(hop, [])[:per_hop])
    return out


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-hop", type=int, default=1)
    p.add_argument("--output-json", default="data/plain_vector_vs_hybrid_stratified.json")
    p.add_argument("--output-md", default="data/plain_vector_vs_hybrid_stratified.md")
    args = p.parse_args()

    validation = validate_v2_dataset(DATASET_FILE, REPO_ROOT / "data" / "corpus" / "chunks.json")
    questions = select(load_v2_questions(), args.per_hop)
    runner = BenchmarkV2Runner(validation["dataset_sha256"])

    vector = []
    hybrid = []
    for q in questions:
        vector.append((await runner.run_plain_vector_question(q)).model_dump())
    for q in questions:
        hybrid.append((await runner.run_hybrid_graphrag_question(q)).model_dump())

    by_id = {r["question_id"]: r for r in hybrid}
    comparison = []
    for vr in vector:
        hr = by_id[vr["question_id"]]
        comparison.append({
            "question_id": vr["question_id"],
            "hop_type": vr["hop_type"],
            "vector": vr,
            "hybrid": hr,
            "fact_score_delta": None if vr.get("fact_score") is None or hr.get("fact_score") is None else round(hr["fact_score"] - vr["fact_score"], 4),
            "retrieval_recall_delta": None if vr.get("retrieval_recall") is None or hr.get("retrieval_recall") is None else round(hr["retrieval_recall"] - vr["retrieval_recall"], 4),
            "latency_delta_ms": round(hr["latency_ms"] - vr["latency_ms"], 1),
        })

    payload = {
        "schema_version": "plain-vs-hybrid-stratified-v1",
        "dataset_sha256": validation["dataset_sha256"],
        "question_count": len(questions),
        "per_question": comparison,
        "methodology": "Same benchmark questions and frozen gold labels; vector and hybrid are executed independently through their real retrieval/synthesis paths.",
    }
    Path(args.output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Plain Vector vs Hybrid GraphRAG — Stratified Fresh Run",
        "",
        f"Questions: **{len(questions)}**; dataset SHA-256: `{validation['dataset_sha256']}`",
        "",
        "| ID | Tier | Vector fact | Hybrid fact | Fact Δ | Vector recall | Hybrid recall | Recall Δ | Vector ms | Hybrid ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def fmt(v): return "N/A" if v is None else f"{v:.3f}"
    for r in comparison:
        v, h = r["vector"], r["hybrid"]
        lines.append(
            f"| `{r['question_id']}` | {r['hop_type']} | {fmt(v.get('fact_score'))} | {fmt(h.get('fact_score'))} | {fmt(r['fact_score_delta'])} | "
            f"{fmt(v.get('retrieval_recall'))} | {fmt(h.get('retrieval_recall'))} | {fmt(r['retrieval_recall_delta'])} | {v['latency_ms']:.1f} | {h['latency_ms']:.1f} |"
        )
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {args.output_json} and {args.output_md}")


if __name__ == "__main__":
    asyncio.run(main())
