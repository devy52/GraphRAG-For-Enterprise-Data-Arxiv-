# -*- coding: utf-8 -*-
"""
Benchmark V2 Execution Driver & Audit Generator.

Architecture Role:
    Executes the Evaluation V2 benchmark comparing Hybrid GraphRAG against
    Plain Vector RAG over the authoritative 50-question fact-level ground truth.
    Produces complete audit records preserving raw evidence, a per-question audit table,
    consolidated V2 results, and an explicit v1 vs v2 comparison breakdown.

Outputs:
    - data/benchmark_results_50q_v2.json
    - data/benchmark_audit_records_v2.jsonl
    - data/benchmark_audit_table_v2.md
    - data/benchmark_comparison_v1_vs_v2.json
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.logging import setup_logger
from src.eval.evaluator_v2 import EvaluatorV2
from src.eval.benchmark_integrity import sha256_file, validate_v2_dataset
from src.eval.models_v2 import BenchmarkQuestionV2, QuestionAuditRecord
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import AnswerSynthesizer
from src.vector.indexer import VectorStore
from src.vector.models import VectorSearchResult

logger = setup_logger(name="benchmark.v2")

DATASET_FILE = REPO_ROOT / "data" / "benchmark_v2_dataset.jsonl"
LEGACY_RESULTS_FILE = REPO_ROOT / "data" / "test_evaluation_bundle" / "benchmark_results_50q.json"
OUTPUT_V2_RESULTS = REPO_ROOT / "data" / "benchmark_results_50q_v2.json"
OUTPUT_AUDIT_JSONL = REPO_ROOT / "data" / "benchmark_audit_records_v2.jsonl"
OUTPUT_AUDIT_MD = REPO_ROOT / "data" / "benchmark_audit_table_v2.md"
OUTPUT_COMPARISON_JSON = REPO_ROOT / "data" / "benchmark_comparison_v1_vs_v2.json"


def extract_graph_evidence_ids(graph_facts: List[str]) -> List[str]:
    """Extract chunk IDs embedded in graph provenance annotations."""
    ids: List[str] = []
    for fact in graph_facts:
        ids.extend(re.findall(r"\[chunk\s*:\s*([^\]]+)\]", fact, flags=re.I))
    return list(dict.fromkeys(ids))


def load_v2_questions() -> List[BenchmarkQuestionV2]:
    questions: List[BenchmarkQuestionV2] = []
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(BenchmarkQuestionV2.model_validate_json(line.strip()))
    return questions


class BenchmarkV2Runner:
    def __init__(self, dataset_sha256: str) -> None:
        self.coordinator = RetrievalCoordinator()
        self.synthesizer = AnswerSynthesizer()
        self.vector_store = self.coordinator.vector_store
        self.dataset_sha256 = dataset_sha256
        self.evaluator = EvaluatorV2()

    async def run_plain_vector_question(self, q: BenchmarkQuestionV2) -> QuestionAuditRecord:
        start_time = time.time()
        error_state = None
        retrieved_chunks: List[VectorSearchResult] = []

        try:
            retrieved_chunks = await self.vector_store.similarity_search(q.question, top_k=5)
        except Exception as e:
            error_state = f"vector_search_err: {str(e)}"
            # Fail closed: never synthesize a fake evidence chunk.
            retrieved_chunks = []

        retrieval_ms = (time.time() - start_time) * 1000.0

        ctx = RetrievalContext(
            query=q.question,
            route=RouteDecision.VECTOR,
            graph_facts=[],
            retrieved_chunks=retrieved_chunks,
            cited_chunk_ids=[c.chunk_id for c in retrieved_chunks],
        )

        try:
            synthesized = await self.synthesizer.synthesize(ctx, use_cache=False)
            total_ms = retrieval_ms + synthesized.latency_ms.get("total_ms", 10.0)
            ans = synthesized.answer
            citations = synthesized.cited_chunk_ids
        except Exception as e:
            error_state = f"synthesis_err: {str(e)}"
            total_ms = retrieval_ms + 10.0
            ans = "I cannot answer this question because there is insufficient evidence in the provided context."
            citations = []

        return self.evaluator.evaluate_question(
            question=q,
            generated_answer=ans,
            retrieved_chunk_ids=[c.chunk_id for c in retrieved_chunks],
            retrieved_chunk_texts=[c.text for c in retrieved_chunks],
            citations=citations,
            latency_ms=total_ms,
            model_name="plain-vector-baseline",
            error_state=error_state,
            dataset_sha256=self.dataset_sha256,
        )

    async def run_hybrid_graphrag_question(self, q: BenchmarkQuestionV2) -> QuestionAuditRecord:
        start_time = time.time()
        error_state = None

        try:
            retrieval_ctx = await self.coordinator.retrieve(q.question)
        except Exception as e:
            error_state = f"coordinator_err: {str(e)}"
            # Fail closed: never inject q.reference_answer or expected facts into context.
            retrieval_ctx = RetrievalContext(
                query=q.question,
                route=RouteDecision.BOTH,
                graph_facts=[],
                retrieved_chunks=[],
                cited_chunk_ids=[],
            )

        elapsed_ms = (time.time() - start_time) * 1000.0

        try:
            synthesized = await self.synthesizer.synthesize(retrieval_ctx, use_cache=False)
            total_ms = max(
                elapsed_ms,
                sum(retrieval_ctx.latency_ms.values()) + sum(synthesized.latency_ms.values()),
                1.0,
            )
            ans = synthesized.answer
            citations = synthesized.cited_chunk_ids
        except Exception as e:
            error_state = f"synthesis_err: {str(e)}"
            total_ms = elapsed_ms + 10.0
            ans = "I cannot answer this question because there is insufficient evidence in the provided context."
            citations = []

        retrieved_ids = [c.chunk_id for c in retrieval_ctx.retrieved_chunks]
        graph_prov_chunk_ids = extract_graph_evidence_ids(retrieval_ctx.graph_facts)
        retrieved_metadata_ids = [m_rec.id for m_rec in getattr(retrieval_ctx, "metadata_records", [])]
        available_evidence_ids = list(dict.fromkeys(retrieved_ids + retrieved_metadata_ids))
        evidence_texts = [c.text for c in retrieval_ctx.retrieved_chunks] + list(retrieval_ctx.graph_facts)
        return self.evaluator.evaluate_question(
            question=q,
            generated_answer=ans,
            retrieved_chunk_ids=retrieved_ids,
            retrieved_chunk_texts=[c.text for c in retrieval_ctx.retrieved_chunks],
            citations=citations,
            latency_ms=total_ms,
            model_name="hybrid-graphrag",
            error_state=error_state,
            available_evidence_ids=available_evidence_ids,
            dataset_sha256=self.dataset_sha256,
            graph_evidence_ids=graph_prov_chunk_ids,
            graph_provenance_chunk_ids=graph_prov_chunk_ids,
            graph_facts=retrieval_ctx.graph_facts,
            evidence_texts=evidence_texts,
            retrieved_metadata_ids=retrieved_metadata_ids,
        )


def _mean(values: List[float]) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


def aggregate_system_records(records: List[QuestionAuditRecord]) -> Dict[str, Any]:
    if not records:
        return {}

    by_hop: Dict[str, List[QuestionAuditRecord]] = {}
    for r in records:
        by_hop.setdefault(r.hop_type, []).append(r)

    answerable_records = [r for r in records if r.answerable and r.fact_evaluable and r.fact_score is not None]
    fact_score_by_hop: Dict[str, Optional[float]] = {}
    for hop, recs in by_hop.items():
        vals = [r.fact_score for r in recs if r.answerable and r.fact_evaluable and r.fact_score is not None]
        fact_score_by_hop[hop] = _mean(vals)

    answerable_accuracy = round(sum(1 for r in records if r.answerable_correct) / len(answerable_records), 4) if answerable_records else None
    unanswerable_records = [r for r in records if not r.answerable]
    abstention_accuracy = round(sum(1 for r in unanswerable_records if r.correctly_abstained) / len(unanswerable_records), 4) if unanswerable_records else None

    retrieval_records = [r for r in records if r.retrieval_evaluable]
    mean_retrieval = {
        "precision": _mean([r.retrieval_precision for r in retrieval_records if r.retrieval_precision is not None]),
        "recall": _mean([r.retrieval_recall for r in retrieval_records if r.retrieval_recall is not None]),
        "mrr": _mean([r.retrieval_mrr for r in retrieval_records if r.retrieval_mrr is not None]),
        "evaluable_questions": len(retrieval_records),
    }

    vec_records = [r for r in records if r.vector_retrieval_evaluable]
    mean_vec_retrieval = {
        "precision": _mean([r.vector_retrieval_precision for r in vec_records if r.vector_retrieval_precision is not None]),
        "recall": _mean([r.vector_retrieval_recall for r in vec_records if r.vector_retrieval_recall is not None]),
        "mrr": _mean([r.vector_retrieval_mrr for r in vec_records if r.vector_retrieval_mrr is not None]),
        "evaluable_questions": len(vec_records),
    }

    graph_records = [r for r in records if r.graph_retrieval_evaluable]
    mean_graph_retrieval = {
        "precision": _mean([r.graph_retrieval_precision for r in graph_records if r.graph_retrieval_precision is not None]),
        "recall": _mean([r.graph_retrieval_recall for r in graph_records if r.graph_retrieval_recall is not None]),
        "mrr": _mean([r.graph_retrieval_mrr for r in graph_records if r.graph_retrieval_mrr is not None]),
        "evaluable_questions": len(graph_records),
    }

    mean_groundedness = _mean([r.context_groundedness for r in records])
    mean_unsupported_rate = _mean([r.unsupported_claim_rate for r in records])
    latencies = [r.latency_ms for r in records]
    p50_lat = round(statistics.median(latencies), 1) if latencies else 0.0
    p95_lat = round(statistics.quantiles(latencies, n=20)[18], 1) if len(latencies) >= 20 else p50_lat * 1.3
    mean_lat = round(statistics.mean(latencies), 1) if latencies else 0.0

    substantive_chunk_records = [r for r in records if r.substantive_chunk_recall is not None]
    metadata_records = [r for r in records if r.metadata_recall is not None]
    unified_records = [r for r in records if r.unified_evidence_recall is not None]

    return {
        "layer_a_retrieval": mean_retrieval,
        "layer_a_unified_retrieval": mean_retrieval,
        "layer_a_vector_retrieval": mean_vec_retrieval,
        "layer_a_graph_retrieval": mean_graph_retrieval,
        "layer_a_substantive_chunk_recall": _mean([r.substantive_chunk_recall for r in substantive_chunk_records]),
        "layer_a_metadata_recall": _mean([r.metadata_recall for r in metadata_records]),
        "layer_a_unified_evidence_recall": _mean([r.unified_evidence_recall for r in unified_records]),
        "layer_b_factual_correctness": {
            "evaluable_answerable_questions": len(answerable_records),
            "fact_score_by_hop": fact_score_by_hop,
            "answerable_only_fact_score": _mean([r.fact_score for r in answerable_records if r.fact_score is not None]),
            "answerable_accuracy_at_threshold_0_70": answerable_accuracy,
        },
        "layer_c_groundedness": {
            "mean_context_groundedness": mean_groundedness,
            "mean_unsupported_claim_rate": mean_unsupported_rate,
            "methods": sorted(set(r.groundedness_method for r in records)),
        },
        "layer_d_answerability": {
            "total_questions": len(records),
            "answerable_questions": len(answerable_records),
            "unanswerable_questions": len(unanswerable_records),
            "answerable_correct": sum(1 for r in records if r.answerable_correct),
            "answerable_incorrect": sum(1 for r in records if r.answerable_incorrect),
            "correctly_abstained": sum(1 for r in records if r.correctly_abstained),
            "incorrectly_abstained": sum(1 for r in records if r.incorrectly_abstained),
            "answerable_accuracy": answerable_accuracy,
            "abstention_accuracy": abstention_accuracy,
            "overall_success_rate": round((sum(1 for r in records if r.answerable_correct) + sum(1 for r in records if r.correctly_abstained)) / len(records), 4),
        },
        "layer_e_efficiency": {
            "p50_latency_ms": p50_lat,
            "p95_latency_ms": p95_lat,
            "mean_latency_ms": mean_lat,
        },
        "lexical_proxies": {
            "mean_reference_text_token_f1": _mean([r.reference_text_token_f1 for r in records]),
            "mean_lexical_chunk_overlap_utilization": _mean([r.lexical_chunk_overlap_utilization for r in records]),
            "mean_invalid_citation_reference_rate": _mean([r.invalid_citation_reference_rate for r in records]),
        },
    }


def generate_markdown_audit_table(records: List[QuestionAuditRecord]) -> str:
    lines = [
        "# Benchmark V2 Per-Question Audit Table",
        "",
        "| Question ID | Hop Type | Answerable | Retrieval Recall | Fact Score | Correct | Missing | Incorrect | Groundedness | Unsupported | Token F1 | Abstention |",
        "|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for r in records:
        ans_str = "Yes" if r.answerable else "No"
        retrieval = "N/A" if r.retrieval_recall is None else f"{r.retrieval_recall:.2f}"
        fact = "N/A" if r.fact_score is None else f"{r.fact_score:.2f}"
        abs_str = "Correct" if r.correctly_abstained else "Incorrect" if r.incorrectly_abstained else "Answered" if r.did_not_abstain else "N/A"
        lines.append(
            f"| `{r.question_id}` | {r.hop_type} | {ans_str} | {retrieval} | {fact} | "
            f"{r.facts_correct} | {r.facts_missing} | {r.facts_incorrect} | {r.context_groundedness:.2f} | "
            f"{r.unsupported_claim_rate:.2f} | {r.reference_text_token_f1:.2f} | {abs_str} |"
        )
    return "\n".join(lines)


async def main() -> None:
    validation = validate_v2_dataset(DATASET_FILE, REPO_ROOT / "data" / "corpus" / "chunks.json")
    dataset_hash = validation["dataset_sha256"]
    questions = load_v2_questions()
    logger.info("Loaded %d questions from %s (sha256=%s)", len(questions), DATASET_FILE, dataset_hash)

    runner = BenchmarkV2Runner(dataset_hash)

    vector_records: List[QuestionAuditRecord] = []
    hybrid_records: List[QuestionAuditRecord] = []

    logger.info("Running Plain Vector Baseline over 50 questions...")
    for q in questions:
        rec = await runner.run_plain_vector_question(q)
        vector_records.append(rec)

    logger.info("Running Hybrid GraphRAG over 50 questions...")
    for q in questions:
        rec = await runner.run_hybrid_graphrag_question(q)
        hybrid_records.append(rec)

    # Save per-question audit records
    OUTPUT_AUDIT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_AUDIT_JSONL, "w", encoding="utf-8") as f:
        for r in vector_records:
            f.write(json.dumps(r.model_dump(), ensure_ascii=False) + "\n")
        for r in hybrid_records:
            f.write(json.dumps(r.model_dump(), ensure_ascii=False) + "\n")
    logger.info("Saved %d total audit records to %s", len(vector_records) + len(hybrid_records), OUTPUT_AUDIT_JSONL)

    # Generate Markdown Audit Table for Hybrid GraphRAG
    table_md = generate_markdown_audit_table(hybrid_records)
    with open(OUTPUT_AUDIT_MD, "w", encoding="utf-8") as f:
        f.write(table_md)
    logger.info("Saved audit markdown table to %s", OUTPUT_AUDIT_MD)

    # Aggregate summaries
    vector_summary = aggregate_system_records(vector_records)
    hybrid_summary = aggregate_system_records(hybrid_records)

    v2_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_name": "RAG-Enterprise-Benchmark-v2",
        "dataset_sha256": dataset_hash,
        "total_questions": len(questions),
        "evaluation_standard": "Decoupled 5-Layer Integrity Standard (V2)",
        "evaluation_status": "fresh_run",
        "vector_baseline": vector_summary,
        "hybrid_graphrag": hybrid_summary,
        "answerable_only_fact_score_delta_points": round(
            ((hybrid_summary["layer_b_factual_correctness"]["answerable_only_fact_score"] or 0.0) -
             (vector_summary["layer_b_factual_correctness"]["answerable_only_fact_score"] or 0.0)) * 100.0, 1
        ),
        "overall_success_rate_delta_points": round(
            (hybrid_summary["layer_d_answerability"]["overall_success_rate"] -
             vector_summary["layer_d_answerability"]["overall_success_rate"]) * 100.0, 1
        ),
    }

    with open(OUTPUT_V2_RESULTS, "w", encoding="utf-8") as f:
        json.dump(v2_results, f, indent=2, ensure_ascii=False)
    logger.info("Saved V2 results to %s", OUTPUT_V2_RESULTS)

    # Build Comparison: V1 vs V2
    comparison: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "legacy_file": str(LEGACY_RESULTS_FILE),
        "v2_file": str(OUTPUT_V2_RESULTS),
        "evaluation_methodology_changes": [
            {
                "metric_group": "Semantic Metrics",
                "change": "faithfulness relabeled to context_groundedness; hallucination_rate relabeled to unsupported_claim_rate.",
                "rationale": "Groundedness measures whether claims are supported by context, not absolute factual truth.",
            },
            {
                "metric_group": "Factual Accuracy",
                "change": "Replaced 'matches > 0' single-keyword rule with weighted required-fact coverage across structured atomic claims.",
                "rationale": "Prevents single irrelevant keyword matches from falsely crediting incorrect answers.",
            },
            {
                "metric_group": "Experimental Hardcoding",
                "change": "Purged all synthetic question-ID overrides (e.g. is_accurate = False for 3-hop vector queries).",
                "rationale": "Restores authentic pipeline measurement without hardcoded synthetic degradation.",
            },
            {
                "metric_group": "Lexical Metrics",
                "change": "Token F1 relabeled reference_text_token_f1 and chunk utilization relabeled lexical_chunk_overlap_utilization.",
                "rationale": "Clarifies that token overlap is a lexical proxy and does not prove semantic evidence utilization.",
            },
            {
                "metric_group": "Answerability",
                "change": "Decoupled answerability into Layer D. Refusals on answerable questions are failures; abstentions on unanswerable questions are successes.",
                "rationale": "Prevents refusals from achieving artificial 100% accuracy.",
            },
        ],
        "v1_metrics_summary": {
            "plain_vector_accuracy": 0.44,
            "hybrid_graphrag_accuracy": 0.62,
            "accuracy_delta": 18.0,
            "note": "Computed using legacy keyword matches > 0 and synthetic 3-hop failure overrides.",
        },
        "v2_metrics_summary": {
            "plain_vector_answerable_only_fact_score": vector_summary["layer_b_factual_correctness"]["answerable_only_fact_score"],
            "hybrid_graphrag_answerable_only_fact_score": hybrid_summary["layer_b_factual_correctness"]["answerable_only_fact_score"],
            "answerable_only_fact_score_delta_points": v2_results["answerable_only_fact_score_delta_points"],
            "plain_vector_success_rate": vector_summary["layer_d_answerability"]["overall_success_rate"],
            "hybrid_graphrag_success_rate": hybrid_summary["layer_d_answerability"]["overall_success_rate"],
            "note": "Factual score is calculated only on answerable questions; abstentions are scored separately in Layer D.",
        },
    }

    with open(OUTPUT_COMPARISON_JSON, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    logger.info("Saved V1 vs V2 comparison to %s", OUTPUT_COMPARISON_JSON)
    print("\nBenchmark V2 execution completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
