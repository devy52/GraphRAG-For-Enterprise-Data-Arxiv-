#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B/C/D Ablation Experiment Driver: Vector vs. Graph vs. Hybrid vs. Oracle.

Architecture Role:
    Executes a rigorous 4-way ablation across benchmark questions to localize the
    source of performance differences (retrieval vs. graph traversal vs. context
    assembly vs. generation).

Modes:
    Mode A (Vector Only):  Dense semantic search -> [retrieved] chunks -> context -> LLM
    Mode B (Graph Only):   Neo4j traversal -> [graph] relational facts -> context -> LLM
    Mode C (Hybrid):       Parallel Vector + Graph -> merged context -> LLM
    Mode D (Oracle):       Exact gold chunk text (no hints, no answers) -> context -> LLM

Telemetry per question per mode:
    - Raw assembled context string
    - Context chunk count & estimated token count
    - Unique evidence IDs & gold evidence coverage
    - Retrieval Precision, Recall, and MRR
    - Answer length (chars & words)
    - Fact proxy score & correctness
    - Correct abstention vs. false refusal
    - Citation validity
    - End-to-end latency profiling

Outputs:
    - data/abcd_ablation_results.json
    - data/abcd_ablation_audit.jsonl
    - data/abcd_ablation_report.md
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.logging import setup_logger
from src.eval.benchmark_integrity import validate_v2_dataset
from src.eval.evaluator_v2 import EvaluatorV2, is_refusal
from src.eval.models_v2 import BenchmarkQuestionV2, QuestionAuditRecord
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import AnswerSynthesizer
from src.vector.models import VectorSearchResult

logger = setup_logger(name="ablation.abcd")


def extract_graph_evidence_ids(graph_facts: List[str]) -> List[str]:
    """Extract chunk IDs embedded in graph provenance annotations."""
    ids: List[str] = []
    for fact in graph_facts:
        ids.extend(re.findall(r"\[chunk\s*:\s*([^\]]+)\]", fact, flags=re.I))
    return list(dict.fromkeys(ids))

DATASET_FILE = REPO_ROOT / "data" / "benchmark_v2_dataset.jsonl"
CHUNKS_FILE = REPO_ROOT / "data" / "corpus" / "chunks.json"
PAPERS_FILE = REPO_ROOT / "data" / "corpus" / "papers.json"
OUTPUT_JSON = REPO_ROOT / "data" / "abcd_ablation_results.json"
OUTPUT_JSONL = REPO_ROOT / "data" / "abcd_ablation_audit.jsonl"
OUTPUT_MD = REPO_ROOT / "data" / "abcd_ablation_report.md"


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate: whitespace words * 1.33 approximation."""
    words = len(text.strip().split())
    return int(round(words * 1.33))


def load_chunks_lookup(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Chunks file missing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        chunks_list = json.load(f)
    return {c["chunk_id"]: c for c in chunks_list}


def load_papers_lookup(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        papers_list = json.load(f)
    return {p["paper_id"]: p for p in papers_list}


def load_questions(path: Path, per_hop: Optional[int] = None) -> List[BenchmarkQuestionV2]:
    questions: List[BenchmarkQuestionV2] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(BenchmarkQuestionV2.model_validate_json(line.strip()))
    if per_hop is None:
        return questions

    order = ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]
    by_hop: Dict[str, List[BenchmarkQuestionV2]] = {}
    for q in questions:
        by_hop.setdefault(q.hop_type, []).append(q)
    selected: List[BenchmarkQuestionV2] = []
    for hop in order:
        selected.extend(by_hop.get(hop, [])[:per_hop])
    return selected


class ABCDAblationRunner:
    def __init__(
        self,
        dataset_sha256: str,
        chunks_lookup: Dict[str, Dict[str, Any]],
        papers_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self.dataset_sha256 = dataset_sha256
        self.chunks_lookup = chunks_lookup
        self.papers_lookup = papers_lookup or {}
        self.coordinator = RetrievalCoordinator()
        self.synthesizer = AnswerSynthesizer()
        self.evaluator = EvaluatorV2()
        if hasattr(self.synthesizer, "cache"):
            self.synthesizer.cache.clear()
        self.coordinator._sessions.clear()

    async def run_mode_a_vector(self, q: BenchmarkQuestionV2) -> Tuple[QuestionAuditRecord, str, Dict[str, Any]]:
        """Mode A: Vector Only."""
        t0 = time.time()
        retrieval_ctx = await self.coordinator.retrieve(
            q.question,
            session_id=f"eval_a_{q.id}",
            forced_route=RouteDecision.VECTOR,
        )
        retrieval_ms = (time.time() - t0) * 1000.0

        assembled_context, _ = self.synthesizer.assemble_context(retrieval_ctx)
        synthesized = await self.synthesizer.synthesize(retrieval_ctx, use_cache=False)
        total_ms = retrieval_ms + synthesized.latency_ms.get("total_ms", 10.0)

        retrieved_ids = [c.chunk_id for c in retrieval_ctx.retrieved_chunks]
        rec = self.evaluator.evaluate_question(
            question=q,
            generated_answer=synthesized.answer,
            retrieved_chunk_ids=retrieved_ids,
            retrieved_chunk_texts=[c.text for c in retrieval_ctx.retrieved_chunks],
            citations=synthesized.cited_chunk_ids,
            latency_ms=total_ms,
            model_name="mode_a_vector",
            dataset_sha256=self.dataset_sha256,
            available_evidence_ids=retrieved_ids,
            evidence_texts=[c.text for c in retrieval_ctx.retrieved_chunks],
        )

        telemetry = {
            "mode": "Mode A (Vector)",
            "context_chunks_count": len(retrieval_ctx.retrieved_chunks),
            "context_tokens_estimate": estimate_tokens(assembled_context),
            "unique_evidence_ids": retrieved_ids,
            "gold_evidence_coverage": rec.retrieval_recall if q.answerable else 1.0,
            "answer_length_chars": len(synthesized.answer),
            "answer_length_words": len(synthesized.answer.split()),
            "latency_ms": round(total_ms, 2),
        }
        return rec, assembled_context, telemetry

    async def run_mode_b_graph(self, q: BenchmarkQuestionV2) -> Tuple[QuestionAuditRecord, str, Dict[str, Any]]:
        """Mode B: Graph Only."""
        t0 = time.time()
        retrieval_ctx = await self.coordinator.retrieve(
            q.question,
            session_id=f"eval_b_{q.id}",
            forced_route=RouteDecision.GRAPH,
        )
        retrieval_ms = (time.time() - t0) * 1000.0

        assembled_context, _ = self.synthesizer.assemble_context(retrieval_ctx)
        synthesized = await self.synthesizer.synthesize(retrieval_ctx, use_cache=False)
        total_ms = retrieval_ms + synthesized.latency_ms.get("total_ms", 10.0)

        graph_evidence_ids = extract_graph_evidence_ids(retrieval_ctx.graph_facts)
        rec = self.evaluator.evaluate_question(
            question=q,
            generated_answer=synthesized.answer,
            retrieved_chunk_ids=[],
            retrieved_chunk_texts=[],
            citations=synthesized.cited_chunk_ids,
            latency_ms=total_ms,
            model_name="mode_b_graph",
            dataset_sha256=self.dataset_sha256,
            graph_facts=retrieval_ctx.graph_facts,
            graph_evidence_ids=graph_evidence_ids,
            available_evidence_ids=graph_evidence_ids,
            evidence_texts=list(retrieval_ctx.graph_facts),
        )

        telemetry = {
            "mode": "Mode B (Graph)",
            "context_chunks_count": len(retrieval_ctx.graph_facts),
            "context_tokens_estimate": estimate_tokens(assembled_context),
            "unique_evidence_ids": graph_evidence_ids,
            "gold_evidence_coverage": rec.retrieval_recall if q.answerable else 1.0,
            "answer_length_chars": len(synthesized.answer),
            "answer_length_words": len(synthesized.answer.split()),
            "latency_ms": round(total_ms, 2),
        }
        return rec, assembled_context, telemetry

    async def run_mode_c_hybrid(self, q: BenchmarkQuestionV2) -> Tuple[QuestionAuditRecord, str, Dict[str, Any]]:
        """Mode C: Hybrid (Vector + Graph)."""
        t0 = time.time()
        retrieval_ctx = await self.coordinator.retrieve(
            q.question,
            session_id=f"eval_c_{q.id}",
            forced_route=RouteDecision.BOTH,
        )
        retrieval_ms = (time.time() - t0) * 1000.0

        assembled_context, _ = self.synthesizer.assemble_context(retrieval_ctx)
        synthesized = await self.synthesizer.synthesize(retrieval_ctx, use_cache=False)
        total_ms = retrieval_ms + synthesized.latency_ms.get("total_ms", 10.0)

        retrieved_ids = [c.chunk_id for c in retrieval_ctx.retrieved_chunks]
        graph_evidence_ids = extract_graph_evidence_ids(retrieval_ctx.graph_facts)
        metadata_ids = [m.id for m in getattr(retrieval_ctx, "metadata_records", [])]
        available_ids = list(dict.fromkeys(retrieved_ids + graph_evidence_ids + metadata_ids))
        metadata_texts = [m.formatted_header for m in getattr(retrieval_ctx, "metadata_records", [])]
        evidence_texts = [c.text for c in retrieval_ctx.retrieved_chunks] + list(retrieval_ctx.graph_facts) + metadata_texts

        rec = self.evaluator.evaluate_question(
            question=q,
            generated_answer=synthesized.answer,
            retrieved_chunk_ids=retrieved_ids,
            retrieved_chunk_texts=[c.text for c in retrieval_ctx.retrieved_chunks],
            citations=synthesized.cited_chunk_ids,
            latency_ms=total_ms,
            model_name="mode_c_hybrid",
            dataset_sha256=self.dataset_sha256,
            graph_facts=retrieval_ctx.graph_facts,
            graph_evidence_ids=graph_evidence_ids,
            retrieved_metadata_ids=metadata_ids,
            available_evidence_ids=available_ids,
            evidence_texts=evidence_texts,
        )

        telemetry = {
            "mode": "Mode C (Hybrid)",
            "context_chunks_count": len(retrieval_ctx.retrieved_chunks) + len(retrieval_ctx.graph_facts) + len(metadata_ids),
            "context_tokens_estimate": estimate_tokens(assembled_context),
            "unique_evidence_ids": available_ids,
            "gold_evidence_coverage": rec.retrieval_recall if q.answerable else 1.0,
            "answer_length_chars": len(synthesized.answer),
            "answer_length_words": len(synthesized.answer.split()),
            "latency_ms": round(total_ms, 2),
            "suppressed_evidence": getattr(retrieval_ctx, "suppressed_evidence", []),
        }
        return rec, assembled_context, telemetry

    async def run_mode_d_oracle(self, q: BenchmarkQuestionV2) -> Tuple[QuestionAuditRecord, str, Dict[str, Any]]:
        """
        Mode D: Oracle Context.
        Constructs Oracle from all authoritative gold evidence (chunks + document metadata + graph facts).
        Zero leakage of reference answers, other required facts, or citations.
        """
        t0 = time.time()
        gold_chunks: List[VectorSearchResult] = []
        retrieved_metadata_ids: List[str] = []
        graph_facts: List[str] = []

        evidence_items = getattr(q, "gold_evidence", [])
        if not evidence_items and q.gold_chunk_ids:
            from src.eval.models_v2 import GoldEvidenceItem, GoldEvidenceType
            evidence_items = [
                GoldEvidenceItem(
                    type=GoldEvidenceType.CHUNK,
                    id=cid,
                    supports=[f.id for f in q.required_facts],
                )
                for cid in q.gold_chunk_ids
            ]

        for item in evidence_items:
            item_type = getattr(item.type, "value", item.type)
            if item_type == "chunk":
                chunk_data = self.chunks_lookup.get(item.id)
                if chunk_data:
                    gold_chunks.append(
                        VectorSearchResult(
                            chunk_id=chunk_data["chunk_id"],
                            document_id=chunk_data.get("document_id", "doc"),
                            text=chunk_data["text"],
                            score=1.0,
                            paper_title=chunk_data.get("paper_title", "Gold Reference Paper"),
                            section_path=chunk_data.get("section_path", "Evidence"),
                        )
                    )
            elif item_type == "metadata":
                doc_id = item.document_id
                paper = self.papers_lookup.get(doc_id)
                if paper:
                    authors = paper.get("authors", [])
                    author_names = [
                        a.get("name", str(a)) if isinstance(a, dict) else str(a)
                        for a in authors
                    ]
                    meta_text = (
                        f"Document Catalog Header:\n"
                        f"Paper Title: {paper.get('title', 'Unknown')}\n"
                        f"Authors: {', '.join(author_names)}\n"
                        f"ArXiv ID: {paper.get('arxiv_id', doc_id)}"
                    )
                    gold_chunks.append(
                        VectorSearchResult(
                            chunk_id=item.id,
                            document_id=doc_id or "meta_doc",
                            text=meta_text,
                            score=1.0,
                            paper_title=paper.get("title", "Document Metadata"),
                            section_path="Document Header Metadata",
                        )
                    )
                    retrieved_metadata_ids.append(item.id)
            elif item_type == "graph_fact":
                if item.text:
                    graph_facts.append(item.text)

        oracle_ctx = RetrievalContext(
            query=q.question,
            route=RouteDecision.BOTH if graph_facts else RouteDecision.VECTOR,
            graph_facts=graph_facts,
            retrieved_chunks=gold_chunks,
            cited_chunk_ids=[c.chunk_id for c in gold_chunks],
        )

        assembled_context, _ = self.synthesizer.assemble_context(oracle_ctx)
        synthesized = await self.synthesizer.synthesize(oracle_ctx, use_cache=False)
        total_ms = (time.time() - t0) * 1000.0

        gold_chunk_ids = [c.chunk_id for c in gold_chunks if not c.chunk_id.startswith("meta_")]
        evidence_ids = [c.chunk_id for c in gold_chunks]
        rec = self.evaluator.evaluate_question(
            question=q,
            generated_answer=synthesized.answer,
            retrieved_chunk_ids=gold_chunk_ids,
            retrieved_chunk_texts=[c.text for c in gold_chunks],
            citations=synthesized.cited_chunk_ids,
            latency_ms=total_ms,
            model_name="mode_d_oracle",
            dataset_sha256=self.dataset_sha256,
            available_evidence_ids=evidence_ids,
            evidence_texts=[c.text for c in gold_chunks] + graph_facts,
            retrieved_metadata_ids=retrieved_metadata_ids,
            graph_facts=graph_facts,
        )

        telemetry = {
            "mode": "Mode D (Oracle)",
            "context_chunks_count": len(gold_chunks) + len(graph_facts),
            "context_tokens_estimate": estimate_tokens(assembled_context),
            "unique_evidence_ids": evidence_ids,
            "gold_evidence_coverage": 1.0 if q.answerable else 1.0,
            "answer_length_chars": len(synthesized.answer),
            "answer_length_words": len(synthesized.answer.split()),
            "latency_ms": round(total_ms, 2),
        }
        return rec, assembled_context, telemetry


def _mean(vals: List[float]) -> Optional[float]:
    return round(statistics.mean(vals), 4) if vals else None


def summarize_mode(records: List[QuestionAuditRecord], telemetries: List[Dict[str, Any]]) -> Dict[str, Any]:
    ans_recs = [r for r in records if r.answerable and r.fact_evaluable and r.fact_score is not None]
    unans_recs = [r for r in records if not r.answerable]

    fact_scores = [r.fact_score for r in ans_recs]
    chunk_recalls = [r.vector_retrieval_recall for r in ans_recs if r.vector_retrieval_evaluable and r.vector_retrieval_recall is not None]
    graph_recalls = [r.graph_retrieval_recall for r in ans_recs if r.graph_retrieval_evaluable and r.graph_retrieval_recall is not None]
    meta_recalls = [r.metadata_retrieval_recall for r in ans_recs if r.metadata_retrieval_evaluable and r.metadata_retrieval_recall is not None]
    unified_recalls = [r.unified_evidence_recall for r in ans_recs if r.unified_evidence_recall is not None]

    precisions = [r.retrieval_precision for r in ans_recs if r.retrieval_precision is not None]
    recalls = [r.retrieval_recall for r in ans_recs if r.retrieval_recall is not None]
    mrrs = [r.retrieval_mrr for r in ans_recs if r.retrieval_mrr is not None]
    latencies = [r.latency_ms for r in records]
    tokens = [t["context_tokens_estimate"] for t in telemetries]
    chunks = [t["context_chunks_count"] for t in telemetries]

    success_count = sum(1 for r in ans_recs if r.fact_score is not None and r.fact_score >= 0.70)
    abstain_count = sum(1 for r in unans_recs if r.correctly_abstained)

    by_tier: Dict[str, Dict[str, Any]] = {}
    for tier in ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]:
        tier_recs = [r for r in records if r.hop_type == tier]
        tier_ans = [r for r in tier_recs if r.answerable and r.fact_evaluable and r.fact_score is not None]
        if tier == "out-of-scope":
            tier_unans = [r for r in tier_recs if not r.answerable]
            corr_abstain = sum(1 for r in tier_unans if r.correctly_abstained)
            by_tier[tier] = {
                "count": len(tier_recs),
                "fact_score_mean": None,
                "abstention_accuracy": round(corr_abstain / len(tier_unans), 4) if tier_unans else None,
            }
        else:
            by_tier[tier] = {
                "count": len(tier_recs),
                "fact_score_mean": _mean([r.fact_score for r in tier_ans]),
                "retrieval_recall_mean": _mean([r.retrieval_recall for r in tier_ans if r.retrieval_recall is not None]),
                "retrieval_precision_mean": _mean([r.retrieval_precision for r in tier_ans if r.retrieval_precision is not None]),
            }

    return {
        "question_count": len(records),
        "answerable_count": len(ans_recs),
        "unanswerable_count": len(unans_recs),
        "fact_score_mean": _mean(fact_scores),
        "answerable_success_rate": round(success_count / len(ans_recs), 4) if ans_recs else None,
        "abstention_accuracy": round(abstain_count / len(unans_recs), 4) if unans_recs else None,
        "chunk_recall_mean": _mean(chunk_recalls),
        "graph_recall_mean": _mean(graph_recalls),
        "metadata_recall_mean": _mean(meta_recalls),
        "unified_recall_mean": _mean(unified_recalls),
        "retrieval_precision_mean": _mean(precisions),
        "retrieval_recall_mean": _mean(recalls),
        "retrieval_mrr_mean": _mean(mrrs),
        "context_tokens_mean": _mean(tokens),
        "context_chunks_mean": _mean(chunks),
        "latency_p50_ms": round(statistics.median(latencies), 2) if latencies else None,
        "latency_p95_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else (round(max(latencies), 2) if latencies else None),
        "by_tier": by_tier,
    }


def classify_hybrid_failure(
    q: BenchmarkQuestionV2,
    rec_v: QuestionAuditRecord,
    rec_h: QuestionAuditRecord,
    rec_o: QuestionAuditRecord,
    tel_h: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Formal Causal Taxonomy Classification (Types A-F):
        A: Correct evidence not retrieved (retrieval recall is 0.0)
        B: Graph traversal found wrong/incomplete evidence (facts retrieved but gold not covered)
        C: Evidence retrieved but assembled in confusing order
        D: Context polluted / drowned by irrelevant evidence (> 800 tokens, precision < 0.2)
        E: Sufficient context present, but LLM failed to synthesize (Oracle succeeded, Hybrid has evidence)
        F: Citation/provenance failure
    """
    if not q.answerable:
        if not rec_h.correctly_abstained:
            return "E", "False positive generation on out-of-scope question"
        return "None", "Correct abstention"

    h_recall = rec_h.retrieval_recall or 0.0
    h_fact = rec_h.fact_score or 0.0
    o_fact = rec_o.fact_score or 0.0
    tokens = tel_h.get("context_tokens_estimate", 0)
    prec = rec_h.retrieval_precision or 0.0

    if h_fact >= 0.70:
        return "None", "Successful generation"

    # Category A: Correct evidence not retrieved
    if h_recall == 0.0:
        if rec_h.graph_facts and len(rec_h.graph_facts) > 0:
            return "B", "Graph traversal found relationships, but missed target gold chunks"
        return "A", "Neither vector search nor graph traversal found the gold chunks"

    # Category D: Context polluted / drowned by irrelevant evidence
    if tokens > 800 and prec < 0.20:
        return "D", f"Context bloated ({tokens} est. tokens) with low precision ({prec:.2f})"

    # Category E: Evidence present in context, Oracle passes, but LLM failed to answer from hybrid
    if h_recall > 0.0 and o_fact >= 0.70:
        return "E", f"Gold chunk retrieved (recall {h_recall:.2f}), Oracle got {o_fact:.2f}, but Hybrid LLM answer failed fact coverage ({h_fact:.2f})"

    # Category C: Multi-hop relation assembly breakdown
    if q.hop_type in ("2-hop", "3-hop", "aggregation") and h_recall > 0.0:
        return "C", "Partial evidence retrieved but relational continuity broken across context blocks"

    # Category F: Citation failure
    if h_fact >= 0.50 and not rec_h.citation_rate:
        return "F", "Factual claims generated but failed strict inline citation validation"

    return "B", "Incomplete evidence retrieved to satisfy all atomic required facts"


async def main() -> None:
    p = argparse.ArgumentParser(description="Run A/B/C/D Ablation across benchmark questions.")
    p.add_argument("--dataset", default=str(DATASET_FILE))
    p.add_argument("--chunks", default=str(CHUNKS_FILE))
    p.add_argument("--output-json", default=str(OUTPUT_JSON))
    p.add_argument("--output-jsonl", default=str(OUTPUT_JSONL))
    p.add_argument("--output-md", default=str(OUTPUT_MD))
    p.add_argument("--per-hop", type=int, default=None, help="If set, evaluates N questions per hop tier")
    args = p.parse_args()

    dataset_path = Path(args.dataset)
    chunks_path = Path(args.chunks)
    out_json = Path(args.output_json)
    out_jsonl = Path(args.output_jsonl)
    out_md = Path(args.output_md)

    # Clean out previous test run artifacts
    for p in (out_json, out_jsonl, out_md):
        if p.exists():
            p.unlink()

    validation = validate_v2_dataset(dataset_path, chunks_path)
    dataset_sha256 = validation["dataset_sha256"]
    print(f"Dataset validated (0 violations). SHA-256: {dataset_sha256}")

    chunks_lookup = load_chunks_lookup(chunks_path)
    papers_lookup = load_papers_lookup(PAPERS_FILE)
    questions = load_questions(dataset_path, args.per_hop)
    print(f"Loaded {len(questions)} questions for A/B/C/D ablation.")

    runner = ABCDAblationRunner(dataset_sha256, chunks_lookup, papers_lookup)

    results_a: List[Tuple[QuestionAuditRecord, str, Dict[str, Any]]] = []
    results_b: List[Tuple[QuestionAuditRecord, str, Dict[str, Any]]] = []
    results_c: List[Tuple[QuestionAuditRecord, str, Dict[str, Any]]] = []
    results_d: List[Tuple[QuestionAuditRecord, str, Dict[str, Any]]] = []

    print("\n--- Executing Mode A (Vector Only) ---")
    for idx, q in enumerate(questions, start=1):
        print(f"[{idx}/{len(questions)}] Mode A: {q.id} ({q.hop_type})")
        res = await runner.run_mode_a_vector(q)
        results_a.append(res)

    print("\n--- Executing Mode B (Graph Only) ---")
    for idx, q in enumerate(questions, start=1):
        print(f"[{idx}/{len(questions)}] Mode B: {q.id} ({q.hop_type})")
        res = await runner.run_mode_b_graph(q)
        results_b.append(res)

    print("\n--- Executing Mode C (Hybrid: Vector + Graph) ---")
    for idx, q in enumerate(questions, start=1):
        print(f"[{idx}/{len(questions)}] Mode C: {q.id} ({q.hop_type})")
        res = await runner.run_mode_c_hybrid(q)
        results_c.append(res)

    print("\n--- Executing Mode D (Oracle Context) ---")
    for idx, q in enumerate(questions, start=1):
        print(f"[{idx}/{len(questions)}] Mode D: {q.id} ({q.hop_type})")
        res = await runner.run_mode_d_oracle(q)
        results_d.append(res)

    # Prepare audit records stream
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for i, q in enumerate(questions):
            record_item = {
                "question_id": q.id,
                "hop_type": q.hop_type,
                "question": q.question,
                "answerable": q.answerable,
                "required_facts": [f.model_dump() for f in q.required_facts],
                "gold_chunk_ids": q.gold_chunk_ids,
                "mode_a_vector": {
                    "audit": results_a[i][0].model_dump(),
                    "context": results_a[i][1],
                    "telemetry": results_a[i][2],
                },
                "mode_b_graph": {
                    "audit": results_b[i][0].model_dump(),
                    "context": results_b[i][1],
                    "telemetry": results_b[i][2],
                },
                "mode_c_hybrid": {
                    "audit": results_c[i][0].model_dump(),
                    "context": results_c[i][1],
                    "telemetry": results_c[i][2],
                },
                "mode_d_oracle": {
                    "audit": results_d[i][0].model_dump(),
                    "context": results_d[i][1],
                    "telemetry": results_d[i][2],
                },
            }
            fh.write(json.dumps(record_item, ensure_ascii=False) + "\n")

    summary_a = summarize_mode([r[0] for r in results_a], [r[2] for r in results_a])
    summary_b = summarize_mode([r[0] for r in results_b], [r[2] for r in results_b])
    summary_c = summarize_mode([r[0] for r in results_c], [r[2] for r in results_c])
    summary_d = summarize_mode([r[0] for r in results_d], [r[2] for r in results_d])

    # Diagnostic triage for worst Hybrid cases (ranked by lowest Hybrid fact score where answerable)
    answerable_indices = [i for i, q in enumerate(questions) if q.answerable]
    hybrid_answerable_ranked = sorted(
        answerable_indices,
        key=lambda i: (results_c[i][0].fact_score if results_c[i][0].fact_score is not None else -1.0),
    )
    worst_10_indices = hybrid_answerable_ranked[:10]

    worst_10_triage = []
    for idx in worst_10_indices:
        q = questions[idx]
        rec_v = results_a[idx][0]
        rec_h = results_c[idx][0]
        rec_o = results_d[idx][0]
        tel_h = results_c[idx][2]
        cat, reasoning = classify_hybrid_failure(q, rec_v, rec_h, rec_o, tel_h)
        retrieval_ok = (rec_h.retrieval_recall or 0.0) > 0.0 or bool(rec_h.graph_facts)
        evidence_ok = (rec_h.retrieval_recall or 0.0) >= 1.0
        context_ok = tel_h["context_tokens_estimate"] <= 800 and cat not in ("C", "D")
        generation_ok = (rec_h.fact_score or 0.0) >= 0.70

        worst_10_triage.append({
            "question_id": q.id,
            "hop_type": q.hop_type,
            "question": q.question,
            "retrieval_stage": "✅" if retrieval_ok else "❌",
            "evidence_stage": "✅" if evidence_ok else "❌",
            "context_stage": "✅" if context_ok else "❌",
            "generation_stage": "✅" if generation_ok else "❌",
            "vector_fact": rec_v.fact_score,
            "hybrid_fact": rec_h.fact_score,
            "oracle_fact": rec_o.fact_score,
            "hybrid_recall": rec_h.retrieval_recall,
            "hybrid_tokens": tel_h["context_tokens_estimate"],
            "failure_type": cat,
            "diagnostic_reasoning": reasoning,
            "generated_answer": rec_h.generated_answer,
            "assembled_context": results_c[idx][1],
        })

    payload = {
        "schema_version": "abcd-ablation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": dataset_sha256,
        "question_count": len(questions),
        "summary": {
            "mode_a_vector": summary_a,
            "mode_b_graph": summary_b,
            "mode_c_hybrid": summary_c,
            "mode_d_oracle": summary_d,
        },
        "worst_10_hybrid_triage": worst_10_triage,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate Markdown Report
    def fmt(val: Optional[float], pct: bool = False) -> str:
        if val is None:
            return "N/A"
        return f"{val * 100:.1f}%" if pct else f"{val:.4f}"

    lines = [
        "# A/B/C/D Ablation Benchmark Report: Isolating Retrieval vs. Generation",
        "",
        f"Generated: `{payload['generated_at']}`  ",
        f"Dataset SHA-256: `{dataset_sha256}`  ",
        f"Total Questions Evaluated: **{len(questions)}**  ",
        "",
        "## 1. High-Level Performance Comparison",
        "",
        "| Metric | Vector | Graph | Hybrid | Oracle |",
        "|---|:---:|:---:|:---:|:---:|",
        f"| **Fact Score** | {fmt(summary_a['fact_score_mean'])} | {fmt(summary_b['fact_score_mean'])} | {fmt(summary_c['fact_score_mean'])} | {fmt(summary_d['fact_score_mean'])} |",
        f"| **Strict Success** | {fmt(summary_a['answerable_success_rate'], pct=True)} | {fmt(summary_b['answerable_success_rate'], pct=True)} | {fmt(summary_c['answerable_success_rate'], pct=True)} | {fmt(summary_d['answerable_success_rate'], pct=True)} |",
        f"| **Chunk Recall** | {fmt(summary_a['chunk_recall_mean'])} | — | {fmt(summary_c['chunk_recall_mean'])} | — |",
        f"| **Graph Recall** | — | {fmt(summary_b['graph_recall_mean'])} | {fmt(summary_c['graph_recall_mean'])} | — |",
        f"| **Metadata Recall** | {fmt(summary_a['metadata_recall_mean'])} | {fmt(summary_b['metadata_recall_mean'])} | {fmt(summary_c['metadata_recall_mean'])} | — |",
        f"| **Unified Recall** | {fmt(summary_a['unified_recall_mean'])} | {fmt(summary_b['unified_recall_mean'])} | {fmt(summary_c['unified_recall_mean'])} | {fmt(summary_d['unified_recall_mean'])} |",
        f"| **Context Tokens (Est)** | {summary_a['context_tokens_mean']} | {summary_b['context_tokens_mean']} | {summary_c['context_tokens_mean']} | {summary_d['context_tokens_mean']} |",
        f"| **Latency p50 (ms)** | {summary_a['latency_p50_ms']} ms | {summary_b['latency_p50_ms']} ms | {summary_c['latency_p50_ms']} ms | {summary_d['latency_p50_ms']} ms |",
        f"| **Latency p95 (ms)** | {summary_a['latency_p95_ms']} ms | {summary_b['latency_p95_ms']} ms | {summary_c['latency_p95_ms']} ms | {summary_d['latency_p95_ms']} ms |",
        f"| **Abstention Accuracy** | {fmt(summary_a['abstention_accuracy'], pct=True)} | {fmt(summary_b['abstention_accuracy'], pct=True)} | {fmt(summary_c['abstention_accuracy'], pct=True)} | {fmt(summary_d['abstention_accuracy'], pct=True)} |",
        "",
        "## 1.1 Causal Attribution Analysis",
        "",
        "- **Retrieval-Caused Failures**: Gaps where required chunks, entities, or metadata were missing from the retrieval candidate pool.",
        "- **Evidence Assembly-Caused Failures**: Cases where evidence was retrieved, but context formatting or token drowning degraded generator synthesis.",
        "- **Ceiling (Oracle)**: Performance achieved when 100% authoritative gold evidence is provided directly to the generator.",
        "",
        "## 2. Per-Tier Fact Score Breakdown",
        "",
        "| Tier | Mode A (Vector) | Mode B (Graph) | Mode C (Hybrid) | Mode D (Oracle) |",
        "|---|---:|---:|---:|---:|",
    ]
    for tier in ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]:
        if tier == "out-of-scope":
            lines.append(
                f"| `{tier}` (Abstention) | {fmt(summary_a['by_tier'][tier]['abstention_accuracy'], pct=True)} | "
                f"{fmt(summary_b['by_tier'][tier]['abstention_accuracy'], pct=True)} | "
                f"{fmt(summary_c['by_tier'][tier]['abstention_accuracy'], pct=True)} | "
                f"{fmt(summary_d['by_tier'][tier]['abstention_accuracy'], pct=True)} |"
            )
        else:
            lines.append(
                f"| `{tier}` | {fmt(summary_a['by_tier'][tier]['fact_score_mean'])} | "
                f"{fmt(summary_b['by_tier'][tier]['fact_score_mean'])} | "
                f"{fmt(summary_c['by_tier'][tier]['fact_score_mean'])} | "
                f"{fmt(summary_d['by_tier'][tier]['fact_score_mean'])} |"
            )

    lines.extend([
        "",
        "## 3. Worst 10 Hybrid Cases Diagnostic Triage",
        "",
        "Taxonomy:",
        "- **Type A**: Correct evidence not retrieved",
        "- **Type B**: Graph traversal found wrong or incomplete evidence",
        "- **Type C**: Evidence retrieved but assembled in confusing order",
        "- **Type D**: Context polluted / drowned by irrelevant evidence",
        "- **Type E**: Sufficient context present, but LLM failed to synthesize",
        "- **Type F**: Citation/provenance failure",
        "",
        "| ID | Tier | Retrieval | Evidence | Context | Generation | Failure | Hybrid Fact | Oracle Fact | Reasoning |",
        "|---|---|:---:|:---:|:---:|:---:|:---:|---:|---:|---|",
    ])
    for item in worst_10_triage:
        lines.append(
            f"| `{item['question_id']}` | {item['hop_type']} | {item['retrieval_stage']} | {item['evidence_stage']} | "
            f"{item['context_stage']} | {item['generation_stage']} | **{item['failure_type']}** | "
            f"{fmt(item['hybrid_fact'])} | {fmt(item['oracle_fact'])} | {item['diagnostic_reasoning']} |"
        )

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nAblation Complete. Artifacts saved:")
    print(f"  JSON: {out_json}")
    print(f"  JSONL: {out_jsonl}")
    print(f"  Markdown: {out_md}")


if __name__ == "__main__":
    asyncio.run(main())
