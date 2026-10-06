#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 31C: Oracle Control Evaluation on 16 Failed Questions.

Architecture Role:
    Evaluates whether supplying exact gold evidence (substantive document passages
    and authoritative catalog records) directly to Qwen2.5-7B-Instruct under identical
    prompt and evaluation settings resolves the 16 failed questions from Run 3B.

Safeguards & Controls:
    1. Generator: Qwen2.5-7B-Instruct with temperature=0.0 (identical to Run 3B).
    2. Prompt Assembly: Identical AnswerSynthesizer.assemble_context templates.
    3. Oracle Context:
       - Exact gold chunk text for every gold type: "chunk" item.
       - Exact authoritative metadata record for every gold type: "metadata" item.
       - Zero reference answer leakage.
       - Zero evaluator hints or labels.
    4. Evaluator: Channel-strict EvaluatorV2 accounting.

Outputs:
    - data/phase31c_oracle_audit.jsonl
    - data/phase31c_oracle_results.json
    - data/phase31c_oracle_report.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.logging import setup_logger
from src.eval.evaluator_v2 import EvaluatorV2
from src.eval.models_v2 import BenchmarkQuestionV2, QuestionAuditRecord
from src.router.metadata_resolver import MetadataEvidenceRecord, MetadataResolver
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import AnswerSynthesizer
from src.vector.models import VectorSearchResult

logger = setup_logger(name="eval.phase31c_oracle")

DATASET_FILE = REPO_ROOT / "data" / "benchmark_v2_dataset.jsonl"
CHUNKS_FILE = REPO_ROOT / "data" / "corpus" / "chunks.json"
PAPERS_FILE = REPO_ROOT / "data" / "corpus" / "papers.json"
RUN3B_AUDIT_FILE = REPO_ROOT / "data" / "run3b_canonical_audit_corrected.jsonl"

OUTPUT_JSONL = REPO_ROOT / "data" / "phase31c_oracle_audit.jsonl"
OUTPUT_JSON = REPO_ROOT / "data" / "phase31c_oracle_results.json"
OUTPUT_MD = REPO_ROOT / "data" / "phase31c_oracle_report.md"

FAILED_QUESTION_IDS = [
    "q_1hop_02", "q_1hop_03",
    "q_2hop_03", "q_2hop_06", "q_2hop_07", "q_2hop_10",
    "q_3hop_03", "q_3hop_05", "q_3hop_06", "q_3hop_08", "q_3hop_09", "q_3hop_10",
    "q_agg_01", "q_agg_02", "q_agg_04", "q_agg_06",
]


def load_chunks_lookup(path: Path) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        chunks_list = json.load(f)
    return {c["chunk_id"]: c for c in chunks_list}


def load_dataset(path: Path) -> Dict[str, BenchmarkQuestionV2]:
    questions: Dict[str, BenchmarkQuestionV2] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = BenchmarkQuestionV2.model_validate_json(line.strip())
                questions[q.id] = q
    return questions


def load_run3b_audit(path: Path) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line.strip())
                records[r["question_id"]] = r
    return records


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


async def run_oracle_for_question(
    question: BenchmarkQuestionV2,
    chunks_lookup: Dict[str, Dict[str, Any]],
    metadata_resolver: MetadataResolver,
    synthesizer: AnswerSynthesizer,
    evaluator: EvaluatorV2,
    dataset_sha256: str,
) -> Tuple[QuestionAuditRecord, str, Dict[str, Any]]:
    t0 = time.time()
    gold_chunks: List[VectorSearchResult] = []
    metadata_records: List[MetadataEvidenceRecord] = []
    retrieved_metadata_ids: List[str] = []

    # Partition typed gold evidence
    evidence_items = getattr(question, "gold_evidence", [])
    if not evidence_items and question.gold_chunk_ids:
        from src.eval.models_v2 import GoldEvidenceItem, GoldEvidenceType
        evidence_items = [
            GoldEvidenceItem(
                type=GoldEvidenceType.CHUNK,
                id=cid,
                supports=[f.id for f in question.required_facts],
            )
            for cid in question.gold_chunk_ids
        ]

    for item in evidence_items:
        itype = getattr(item.type, "value", item.type)
        if itype == "chunk":
            chunk_data = chunks_lookup.get(item.id)
            if chunk_data:
                gold_chunks.append(
                    VectorSearchResult(
                        chunk_id=chunk_data["chunk_id"],
                        document_id=chunk_data.get("document_id", "doc"),
                        text=chunk_data["text"],
                        score=1.0,
                        paper_title=chunk_data.get("paper_title", "Authoritative Document"),
                        section_path=chunk_data.get("section_path", "Section"),
                    )
                )
            else:
                logger.warning("Gold chunk %s missing from corpus lookup!", item.id)
        elif itype == "metadata":
            doc_id = getattr(item, "document_id", None)
            matched_entry = None
            if doc_id and doc_id in metadata_resolver._papers_by_id:
                matched_entry = metadata_resolver._papers_by_id[doc_id]
            else:
                for entry in metadata_resolver._papers_by_id.values():
                    if entry["canonical_id"] == item.id:
                        matched_entry = entry
                        break

            if matched_entry:
                authors_str = ", ".join(matched_entry["authors"])
                header_lines = [
                    "Document Catalog Header:",
                    f"Paper Title: {matched_entry['title']}",
                    f"Authors: {authors_str}",
                ]
                if matched_entry["arxiv_id"]:
                    header_lines.append(f"ArXiv ID: {matched_entry['arxiv_id']}")
                if matched_entry["venue"]:
                    venue_str = matched_entry["venue"]
                    if matched_entry["published_year"]:
                        venue_str += f" ({matched_entry['published_year']})"
                    header_lines.append(f"Venue: {venue_str}")

                m_rec = MetadataEvidenceRecord(
                    id=matched_entry["canonical_id"],
                    paper_id=matched_entry["paper_id"],
                    source="papers.json",
                    field="authors",
                    title=matched_entry["title"],
                    authors=matched_entry["authors"],
                    published_year=matched_entry["published_year"],
                    venue=matched_entry["venue"],
                    arxiv_id=matched_entry["arxiv_id"],
                    formatted_header="\n".join(header_lines),
                )
                metadata_records.append(m_rec)
                retrieved_metadata_ids.append(m_rec.id)
            else:
                logger.warning("Gold metadata record %s missing from catalog!", item.id)

    # Build Oracle RetrievalContext strictly from gold evidence
    all_allowed_ids = [c.chunk_id for c in gold_chunks] + retrieved_metadata_ids
    oracle_ctx = RetrievalContext(
        query=question.question,
        route=RouteDecision.BOTH if metadata_records else RouteDecision.VECTOR,
        graph_facts=[],
        retrieved_chunks=gold_chunks,
        metadata_records=metadata_records,
        cited_chunk_ids=all_allowed_ids,
    )

    assembled_context, _ = synthesizer.assemble_context(oracle_ctx)
    synthesized = await synthesizer.synthesize(oracle_ctx, use_cache=False)
    total_ms = (time.time() - t0) * 1000.0

    # Evaluate using channel-strict EvaluatorV2
    rec = evaluator.evaluate_question(
        question=question,
        generated_answer=synthesized.answer,
        retrieved_chunk_ids=[c.chunk_id for c in gold_chunks],
        retrieved_chunk_texts=[c.text for c in gold_chunks],
        citations=synthesized.cited_chunk_ids,
        latency_ms=total_ms,
        model_name="oracle_control_qwen7b",
        dataset_sha256=dataset_sha256,
        available_evidence_ids=all_allowed_ids,
        evidence_texts=[c.text for c in gold_chunks] + [m.formatted_header for m in metadata_records],
        retrieved_metadata_ids=retrieved_metadata_ids,
        graph_facts=[],
        graph_provenance_chunk_ids=[],
    )

    telemetry = {
        "context_chunks_count": len(gold_chunks),
        "context_metadata_count": len(metadata_records),
        "context_chars": len(assembled_context),
        "answer_chars": len(synthesized.answer),
        "latency_ms": round(total_ms, 2),
        "validation_attempts": synthesized.generation_attempts,
    }
    return rec, assembled_context, telemetry


async def main() -> None:
    logger.info("Initializing Phase 31C Oracle Control Experiment...")
    dataset_sha256 = compute_sha256(DATASET_FILE)
    chunks_lookup = load_chunks_lookup(CHUNKS_FILE)
    questions = load_dataset(DATASET_FILE)
    run3b_audit = load_run3b_audit(RUN3B_AUDIT_FILE)
    metadata_resolver = MetadataResolver()
    synthesizer = AnswerSynthesizer()
    evaluator = EvaluatorV2(enable_semantic_judge=True)

    target_questions = [questions[qid] for qid in FAILED_QUESTION_IDS if qid in questions]
    logger.info("Loaded %d target failure questions for Oracle evaluation.", len(target_questions))

    results: List[Dict[str, Any]] = []
    audit_records: List[QuestionAuditRecord] = []

    print(f"\n{'='*80}")
    print(f"PHASE 31C: ORACLE CONTROL ON {len(target_questions)} FAILED QUESTIONS")
    print(f"{'='*80}\n")

    for idx, q in enumerate(target_questions, start=1):
        r3b_rec = run3b_audit.get(q.id, {})
        r3b_fact = r3b_rec.get("fact_score", 0.0)
        r3b_ans = r3b_rec.get("generated_answer", "")

        print(f"[{idx}/{len(target_questions)}] {q.id} ({q.hop_type})")
        print(f"  Q: {q.question}")
        print(f"  Run 3B Fact Score: {r3b_fact:.4f}")

        audit_rec, assembled_context, telemetry = await run_oracle_for_question(
            question=q,
            chunks_lookup=chunks_lookup,
            metadata_resolver=metadata_resolver,
            synthesizer=synthesizer,
            evaluator=evaluator,
            dataset_sha256=dataset_sha256,
        )
        audit_records.append(audit_rec)

        oracle_fact = audit_rec.fact_score or 0.0
        delta = oracle_fact - r3b_fact

        # Interpret status based on predetermined rules
        if r3b_fact == 0.0:
            if oracle_fact >= 0.70:
                interpretation = "Fail -> Pass (Retrieval/Context Deficiency)"
            else:
                interpretation = "Fail -> Fail (Generator / Evaluator / Formulation Issue)"
        else:  # partial failure
            if oracle_fact > r3b_fact:
                interpretation = "Partial -> Better (Retrieval Deficiency Contributed Materially)"
            else:
                interpretation = "Partial -> Same (Downstream Reasoning / Evidence Formulation Issue)"

        print(f"  Oracle Fact Score: {oracle_fact:.4f} (Delta: {delta:+.4f})")
        print(f"  Interpretation: {interpretation}")
        print(f"  Oracle Answer: {audit_rec.generated_answer[:120]}...\n")

        results.append({
            "question_id": q.id,
            "hop_type": q.hop_type,
            "question": q.question,
            "run3b_fact_score": r3b_fact,
            "run3b_substantive_recall": r3b_rec.get("substantive_chunk_recall"),
            "run3b_unified_recall": r3b_rec.get("unified_evidence_recall"),
            "run3b_answer": r3b_ans,
            "oracle_fact_score": oracle_fact,
            "oracle_substantive_recall": audit_rec.substantive_chunk_recall,
            "oracle_unified_recall": audit_rec.unified_evidence_recall,
            "oracle_answer": audit_rec.generated_answer,
            "fact_delta": round(delta, 4),
            "interpretation": interpretation,
            "telemetry": telemetry,
        })

    # Summary Statistics
    r3b_mean_fact = round(sum(r["run3b_fact_score"] for r in results) / len(results), 4)
    oracle_mean_fact = round(sum(r["oracle_fact_score"] for r in results) / len(results), 4)
    r3b_strict_passes = sum(1 for r in results if r["run3b_fact_score"] >= 0.70)
    oracle_strict_passes = sum(1 for r in results if r["oracle_fact_score"] >= 0.70)

    interpretations_count: Dict[str, int] = {}
    for r in results:
        key = r["interpretation"].split("(")[0].strip()
        interpretations_count[key] = interpretations_count.get(key, 0) + 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_evaluated": len(results),
        "run3b_mean_fact_score": r3b_mean_fact,
        "oracle_mean_fact_score": oracle_mean_fact,
        "fact_score_absolute_delta": round(oracle_mean_fact - r3b_mean_fact, 4),
        "run3b_strict_passes": r3b_strict_passes,
        "oracle_strict_passes": oracle_strict_passes,
        "interpretations": interpretations_count,
        "results": results,
    }

    # Save outputs
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for rec in audit_records:
            f.write(rec.model_dump_json() + "\n")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate Markdown Report
    lines = [
        "# Phase 31C Evaluation Report: Oracle Control on 16 Failed Questions",
        "",
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        "**Generator**: Qwen2.5-7B-Instruct (temperature=0.0, identical prompt/validation templates)  ",
        "**Evaluator**: EvaluatorV2 (Channel-Strict Accounting, ADR 057)  ",
        f"**Dataset SHA256**: `{dataset_sha256}`  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Run 3B Baseline (16 Failures) | Phase 31C Oracle Control | Absolute Delta |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Mean Fact Score** | **{r3b_mean_fact:.4f}** | **{oracle_mean_fact:.4f}** | **{oracle_mean_fact - r3b_mean_fact:+.4f}** |",
        f"| **Strict Passes (Fact Score >= 0.70)** | **{r3b_strict_passes}/{len(results)} ({r3b_strict_passes/len(results)*100:.1f}%)** | **{oracle_strict_passes}/{len(results)} ({oracle_strict_passes/len(results)*100:.1f}%)** | **+{oracle_strict_passes - r3b_strict_passes}** |",
        "",
        "### Categorization Breakdown",
        "",
    ]
    for k, v in interpretations_count.items():
        lines.append(f"- **{k}**: {v}/{len(results)} ({v/len(results)*100:.1f}%)")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Per-Question Results Table",
        "",
        "| ID | Hop Type | Run 3B Fact | Oracle Fact | Delta | Interpretation |",
        "| :--- | :--- | :---: | :---: | :---: | :--- |",
    ])
    for r in results:
        lines.append(
            f"| `{r['question_id']}` | {r['hop_type']} | {r['run3b_fact_score']:.4f} | "
            f"**{r['oracle_fact_score']:.4f}** | {r['fact_delta']:+.4f} | {r['interpretation']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Detailed Case Analysis",
        "",
    ])
    for r in results:
        lines.extend([
            f"### `{r['question_id']}` ({r['hop_type']})",
            f"**Question**: {r['question']}  ",
            f"**Run 3B Score**: {r['run3b_fact_score']:.4f} | **Oracle Score**: {r['oracle_fact_score']:.4f}  ",
            f"**Outcome**: {r['interpretation']}  ",
            "",
            "**Run 3B Generated Answer**:",
            f"> {r['run3b_answer']}",
            "",
            "**Oracle Generated Answer**:",
            f"> {r['oracle_answer']}",
            "",
            "---",
            "",
        ])

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nExecution finished! Summary saved to {OUTPUT_JSON}")
    print(f"Audit log saved to {OUTPUT_JSONL}")
    print(f"Markdown report saved to {OUTPUT_MD}")


if __name__ == "__main__":
    asyncio.run(main())
