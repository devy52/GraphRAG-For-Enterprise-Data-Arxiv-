import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import sys
sys.path.insert(0, "evalharness")
from pathlib import Path
import tempfile

import tests.test_all_basic_metrics as t

print("1. Running test_ndcg_at_k_calculation...")
t.test_ndcg_at_k_calculation()
print("   -> PASSED")

print("2. Running test_rag_evaluator_all_metrics_including_context_recall_and_correctness...")
t.test_rag_evaluator_all_metrics_including_context_recall_and_correctness()
print("   -> PASSED")

print("3. Running test_traditional_nlp_metrics_bleu_rouge_bertscore...")
t.test_traditional_nlp_metrics_bleu_rouge_bertscore()
print("   -> PASSED")

print("4. Running test_runner_computes_and_aggregates_all_10_metrics...")
with tempfile.TemporaryDirectory() as td:
    t.test_runner_computes_and_aggregates_all_10_metrics(Path(td), None)
print("   -> PASSED")

print("5. Running GraphRAG evaluation dimensions (utilization, coherence, diversity, coverage)...")
import tests.test_graph_metrics as tg
tg.test_graph_utilization_rate_calculation()
tg.test_global_diversity_and_thematic_coverage()
tg.test_entity_relation_coverage_sets()
tg.test_graph_evaluator_direct_evaluation()
with tempfile.TemporaryDirectory() as td:
    tg.test_runner_with_graph_track(Path(td))
print("   -> PASSED")

print("\nAll 10 basic metrics + GraphRAG evaluation dimensions verified computing and aggregating successfully!")
