"""
Recompute Run 3B metrics using corrected channel-strict evidence accounting (Phase 31B).
Preserves the exact frozen Run 3B answers and fact evaluations, updating Layer A retrieval metrics.
"""

import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eval.evaluator_v2 import EvaluatorV2
from src.eval.models_v2 import BenchmarkQuestionV2, QuestionAuditRecord
from scripts.run_benchmark_v2 import aggregate_system_records, extract_graph_evidence_ids


def main():
    audit_file = Path("data/run3b_canonical_audit.jsonl")
    dataset_file = Path("data/benchmark_v2_dataset.jsonl")
    out_audit = Path("data/run3b_canonical_audit_corrected.jsonl")
    out_results = Path("data/run3b_canonical_hybrid_results_corrected.json")

    # Load gold dataset
    dataset: Dict[str, BenchmarkQuestionV2] = {}
    with open(dataset_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                dataset[d["id"]] = BenchmarkQuestionV2(**d)

    evaluator = EvaluatorV2(enable_semantic_judge=False)

    updated_records: List[QuestionAuditRecord] = []

    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            qid = item["question_id"]
            q = dataset[qid]
            audit = item.get("audit", {})

            # Exact frozen Run 3B artifacts
            retrieved_chunk_ids = audit.get("retrieved_chunk_ids", [])
            retrieved_chunk_texts = audit.get("retrieved_chunk_texts", [])
            citations = audit.get("citations", [])
            metadata_ids = audit.get("metadata_evidence_ids", [])
            graph_facts = audit.get("graph_facts", [])
            latency_ms = audit.get("latency_ms", 0.0)
            generated_answer = audit.get("generated_answer", "")

            # Re-evaluate with corrected EvaluatorV2
            record = evaluator.evaluate_question(
                question=q,
                generated_answer=generated_answer,
                retrieved_chunk_ids=retrieved_chunk_ids,
                retrieved_chunk_texts=retrieved_chunk_texts,
                citations=citations,
                latency_ms=latency_ms,
                model_name="hybrid-graphrag-run3b-frozen",
                dataset_sha256="",
                graph_evidence_ids=extract_graph_evidence_ids(graph_facts),
                graph_provenance_chunk_ids=extract_graph_evidence_ids(graph_facts),
                graph_facts=graph_facts,
                retrieved_metadata_ids=metadata_ids,
            )

            # Preserve the frozen Run 3B fact evaluations & groundedness (which used semantic judge)
            record.fact_evaluable = audit.get("fact_evaluable", record.fact_evaluable)
            record.fact_score = audit.get("fact_score", record.fact_score)
            record.facts_correct = audit.get("facts_correct", record.facts_correct)
            record.facts_missing = audit.get("facts_missing", record.facts_missing)
            record.facts_incorrect = audit.get("facts_incorrect", record.facts_incorrect)
            record.facts_total = audit.get("facts_total", record.facts_total)
            record.fact_coverage = audit.get("fact_coverage", record.fact_coverage)
            record.satisfied_fact_ids = audit.get("satisfied_fact_ids", record.satisfied_fact_ids)
            record.missing_fact_ids = audit.get("missing_fact_ids", record.missing_fact_ids)
            record.incorrect_fact_ids = audit.get("incorrect_fact_ids", record.incorrect_fact_ids)
            record.fact_verdicts = audit.get("fact_verdicts", record.fact_verdicts)
            record.fact_evaluation_method = audit.get("fact_evaluation_method", record.fact_evaluation_method)
            record.context_groundedness = audit.get("context_groundedness", record.context_groundedness)
            record.unsupported_claim_rate = audit.get("unsupported_claim_rate", record.unsupported_claim_rate)
            record.groundedness_method = audit.get("groundedness_method", record.groundedness_method)
            record.answerable_correct = audit.get("answerable_correct", record.answerable_correct)
            record.answerable_incorrect = audit.get("answerable_incorrect", record.answerable_incorrect)
            record.abstention_correct = audit.get("abstention_correct", record.abstention_correct)
            record.correctly_abstained = audit.get("correctly_abstained", record.correctly_abstained)
            record.incorrectly_abstained = audit.get("incorrectly_abstained", record.incorrectly_abstained)
            record.prompt_tokens = audit.get("prompt_tokens", record.prompt_tokens)
            record.completion_tokens = audit.get("completion_tokens", record.completion_tokens)

            updated_records.append(record)

    # Save corrected audit log
    with open(out_audit, "w", encoding="utf-8") as f:
        for r in updated_records:
            f.write(json.dumps(r.model_dump(), default=str) + "\n")

    # Compute aggregated metrics
    summary = aggregate_system_records(updated_records)
    with open(out_results, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print("=" * 80)
    print("PHASE 31B: FROZEN RUN 3B RECOMPUTATION UNDER CHANNEL-STRICT ACCOUNTING")
    print("=" * 80)
    print(f"Total questions evaluated: {len(updated_records)}")
    
    ans_records = [r for r in updated_records if r.answerable]
    print(f"Answerable questions:      {len(ans_records)}")
    print(f"Overall Fact Score:        {summary['layer_b_factual_correctness']['answerable_only_fact_score']:.4f}")
    print(f"Strict Success Rate:       {summary['layer_d_answerability']['overall_success_rate'] * 100:.1f}%")
    print(f"Substantive Chunk Recall:  {summary['layer_a_substantive_chunk_recall']:.4f}")
    print(f"Metadata Recall:           {summary['layer_a_metadata_recall']:.4f}")
    print(f"Graph Fact Recall:         {summary['layer_a_graph_retrieval']['recall']}")
    print(f"Unified Evidence Recall:   {summary['layer_a_unified_evidence_recall']:.4f}")
    print("-" * 80)
    print("Fact Score by Hop:")
    for hop, score in summary['layer_b_factual_correctness']['fact_score_by_hop'].items():
        print(f"  {hop:12s}: {score}")


if __name__ == "__main__":
    main()
