"""
Compile Evaluation Results Bundle into a self-contained ZIP archive for GPT / AI Reviewers.

Authoritative Artifacts Packed:
- Comprehensive Review Guide (Markdown)
- Evalkit Report (Markdown with full metric descriptions)
- Evalkit Results (Machine-readable JSON)
- Evalkit Configuration (YAML)
- Benchmark Dataset v2 (Gold JSONL)
- Benchmark Audit Records v2 (JSONL)
- Benchmark Audit Table v2 (Markdown)
- Empirical Ragas vs Evalkit Comparison (Markdown & JSON)
- Evaluation V2 Audit Findings & Fixes Applied (Markdown)
- System Architecture & Ontology Specifications (Markdown)
- Corpus Papers & Sample Chunks (JSON)
"""

import hashlib
import json
from pathlib import Path
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = REPO_ROOT / "GraphRAG_Evaluation_Results_Bundle.zip"

FILES_TO_PACK = [
    # Master GPT Review Guides
    ("GPT_REVIEW_GUIDE.md", "GPT_REVIEW_GUIDE.md"),
    ("data/EVALUATION_SUMMARY_FOR_GPT.md", "data/EVALUATION_SUMMARY_FOR_GPT.md"),
    
    # Authoritative Evalkit Results & Reports
    ("data/evalkit_report.md", "data/evalkit_report.md"),
    ("data/evalkit_results.json", "data/evalkit_results.json"),
    ("evalkit_config.yaml", "evalkit_config.yaml"),
    ("run_evalkit.py", "run_evalkit.py"),
    ("evalkit/__init__.py", "evalkit/__init__.py"),
    
    # Stratified Benchmark Dataset & Audit Trail
    ("data/benchmark_v2_dataset.jsonl", "data/benchmark_v2_dataset.jsonl"),
    ("data/benchmark_audit_records_v2.jsonl", "data/benchmark_audit_records_v2.jsonl"),
    ("data/benchmark_audit_table_v2.md", "data/benchmark_audit_table_v2.md"),
    ("data/benchmark_results_50q_v2.json", "data/benchmark_results_50q_v2.json"),
    ("data/EVALUATION_ARTIFACT_STATUS.md", "data/EVALUATION_ARTIFACT_STATUS.md"),
    
    # Empirical Ragas & DeepEval 3-Way Comparison & Frozen Snapshot
    ("data/eval_framework_snapshot.jsonl", "data/eval_framework_snapshot.jsonl"),
    ("data/evalkit_vs_ragas_comparison.md", "data/evalkit_vs_ragas_comparison.md"),
    ("data/evalkit_vs_ragas_comparison.json", "data/evalkit_vs_ragas_comparison.json"),
    ("data/eval_framework_comparison_3way.md", "data/eval_framework_comparison_3way.md"),
    ("data/eval_framework_comparison_3way.json", "data/eval_framework_comparison_3way.json"),
    ("data/plain_vector_vs_hybrid_stratified.md", "data/plain_vector_vs_hybrid_stratified.md"),
    ("data/plain_vector_vs_hybrid_stratified.json", "data/plain_vector_vs_hybrid_stratified.json"),
    
    # A/B/C/D Ablation Study
    ("data/abcd_ablation_results.json", "data/abcd_ablation_results.json"),
    ("data/abcd_ablation_audit.jsonl", "data/abcd_ablation_audit.jsonl"),
    ("data/abcd_ablation_report.md", "data/abcd_ablation_report.md"),
    ("scripts/run_abcd_ablation.py", "scripts/run_abcd_ablation.py"),
    
    # Integrity Audit & Verification Evidence
    ("Docs/EVALUATION_V2_AUDIT_FINDINGS.md", "Docs/EVALUATION_V2_AUDIT_FINDINGS.md"),
    ("Docs/EVALUATION_V2_FIXES_APPLIED.md", "Docs/EVALUATION_V2_FIXES_APPLIED.md"),
    ("Docs/THREE_WAY_EVALUATION.md", "Docs/THREE_WAY_EVALUATION.md"),
    ("Docs/ARCHITECTURE.md", "Docs/ARCHITECTURE.md"),
    ("Docs/DECISIONS.md", "Docs/DECISIONS.md"),
    ("Docs/ONTOLOGY.md", "Docs/ONTOLOGY.md"),
    ("Docs/FLOWS.md", "Docs/FLOWS.md"),
    ("Docs/CODEBASE_MAP.md", "Docs/CODEBASE_MAP.md"),
    ("requirements-evaluation.txt", "requirements-evaluation.txt"),
    
    # Domain Corpus Chunks
    ("data/corpus/papers.json", "data/corpus/papers.json"),
    ("data/corpus/chunks.json", "data/corpus/chunks.json"),
    ("data/corpus/sample_chunks.json", "data/corpus/sample_chunks.json"),
]


def create_bundle() -> None:
    print(f"=== Packing Evaluation Results Bundle: {OUTPUT_ZIP.name} ===")
    packed_files = []
    
    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src_rel, arc_name in FILES_TO_PACK:
            src_path = REPO_ROOT / src_rel
            if not src_path.exists():
                print(f"  [WARN] Missing file: {src_rel}, skipping")
                continue
            zf.write(src_path, arc_name)
            size_kb = src_path.stat().st_size / 1024.0
            print(f"  + Added: {arc_name:<45} ({size_kb:>8.1f} KB)")
            packed_files.append(arc_name)
            
    zip_bytes = OUTPUT_ZIP.read_bytes()
    sha256_hash = hashlib.sha256(zip_bytes).hexdigest()
    total_size_mb = len(zip_bytes) / (1024.0 * 1024.0)
    
    print("\n=== Bundle Packaging Complete ===")
    print(f"Archive Path : {OUTPUT_ZIP}")
    print(f"Archive Size : {total_size_mb:.2f} MB ({len(zip_bytes):,} bytes)")
    print(f"SHA-256 Hash : {sha256_hash}")
    print(f"Total Files  : {len(packed_files)}")


if __name__ == "__main__":
    create_bundle()
