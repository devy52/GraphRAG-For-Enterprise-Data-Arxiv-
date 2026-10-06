# -*- coding: utf-8 -*-
"""
Comprehensive Evaluation Script — Full Benchmark via Evalkit.

Architecture Role:
    Standalone evaluation harness that exercises the complete GraphRAG system
    against all 50 canonical benchmark questions using every available evalkit
    track (rag, text_similarity, retrieval). Produces stratified per-hop-type
    breakdowns, a consolidated JSON report, and a human-readable Markdown
    summary with score legitimacy annotations.

Inputs:
    - CLI flags: --mode (dummy|live), --judge-model, --limit, --output-dir
    - data/evalkit_dataset.jsonl (50-question canonical dataset)
    - eval_adapter.py:GraphRAGAdapter

Outputs:
    - <output-dir>/full_eval_results.json   (machine-readable per-example scores)
    - <output-dir>/full_eval_report.md       (human-readable stratified report)
    - <output-dir>/spot_check_samples.md     (random samples for manual verification)

Design Decisions:
    - Runs all 3 deterministic tracks (text_similarity, retrieval, rag) in
      sequence rather than parallel to avoid adapter resource contention.
    - Annotates every metric with a legitimacy tag:
        "deterministic" = algorithmically computed, always legit
        "judge-scored"  = LLM judge scored, only legit with real judge backend
        "pseudo-random" = dummy judge, NOT a real quality signal
    - Spot-check sampler picks 5 random examples and formats them for manual
      human review (question, reference, system answer, retrieved context).

How it fits the architecture:
    This script is a new standalone test driver in scripts/. It does NOT
    modify any core src/ files. It imports from evalkit_upgraded/ and
    eval_adapter.py, both of which are already in the repo root.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup: ensure repo root and evalkit_upgraded are importable
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVALKIT_PATH = _REPO_ROOT / "evalkit"
if str(_EVALKIT_PATH) not in sys.path:
    sys.path.insert(0, str(_EVALKIT_PATH))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evalkit.contracts.adapter import AdapterResponse
from evalkit.contracts.judge_backend import BaseJudgeBackend
from evalkit.core.config import EvalConfig
from evalkit.core.dataset import load_dataset
from evalkit.core.registry import registry

# Force evalkit built-ins to register
import evalkit  # noqa: F401
import os
import re
from dotenv import load_dotenv

load_dotenv()


# ===========================================================================
# Live Judge Backend (OpenAI-compatible / NVIDIA NIM)
# ===========================================================================

class OpenAICompatibleJudge(BaseJudgeBackend):
    """
    Live LLM Judge using configured OpenAI-compatible API gateway (NVIDIA NIM / OpenRouter).
    Scores prompts and parses JSON score from 0.0 to 1.0.
    """

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        import openai

        self.model = model or os.getenv("EXTRACTION_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        api_key = os.getenv("LLM_API_KEY", "")
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)

    def score(self, prompt: str) -> float:
        messages = [
            {
                "role": "user",
                "content": (
                    f"{prompt.rstrip()}\n\n"
                    "Return ONLY a JSON object with this exact shape: "
                    '{"score": 0.85, "reasoning": "brief justification"}. '
                    "The score must be a number from 0.0 to 1.0."
                ),
            }
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""
        except Exception:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""

        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            score = float(data["score"])
            return max(0.0, min(1.0, score))
        except Exception:
            m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', content)
            if m:
                return max(0.0, min(1.0, float(m.group(1))))
            m2 = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", content)
            if m2:
                return float(m2.group(1))
            return 0.5


registry.register_judge_backend("openai_compatible", OpenAICompatibleJudge)



# ===========================================================================
# Constants
# ===========================================================================

# Which evalkit tracks to run, in order. Each track maps to a registered
# evaluator class in evalkit's registry.
TRACKS = ["text_similarity", "retrieval", "rag"]

# Per-metric legitimacy classification.
# "deterministic" = pure math, always valid.
# "judge-scored"  = requires real LLM judge.
METRIC_LEGITIMACY: dict[str, str] = {
    # text_similarity track (all deterministic)
    "exact_match": "deterministic",
    "f1": "deterministic",
    "bleu": "deterministic",
    "rouge_l": "deterministic",
    "embedding_similarity": "judge-scored",  # uses LiteLLM embeddings
    # retrieval track (all deterministic)
    "precision_at_k": "deterministic",
    "recall_at_k": "deterministic",
    "mrr": "deterministic",
    "chunk_utilization": "deterministic",
    # rag track (all judge-scored)
    "faithfulness": "judge-scored",
    "context_precision": "judge-scored",
    "answer_relevancy": "judge-scored",
    "hallucination_rate": "judge-scored",
}

# Hop type ordering for consistent report display
HOP_ORDER = ["1-hop", "2-hop", "3-hop", "aggregation", "out-of-scope"]

# Number of spot-check samples to include for manual verification
SPOT_CHECK_COUNT = 5

# Per-track default metrics, used to build filtered lists
_TRACK_ALL_METRICS: dict[str, list[str]] = {
    "text_similarity": ["exact_match", "f1", "bleu", "rouge_l", "embedding_similarity"],
    "retrieval": ["precision_at_k", "recall_at_k", "mrr", "chunk_utilization"],
    "rag": ["faithfulness", "context_precision", "answer_relevancy", "hallucination_rate"],
}


def _get_track_metrics(
    track_name: str, user_filter: list[str] | None
) -> list[str] | None:
    """
    Returns the metric list for a given track, removing metrics whose
    dependencies are not installed. Returns None if no filtering needed.
    """
    all_metrics = _TRACK_ALL_METRICS.get(track_name)
    if all_metrics is None:
        return user_filter  # unknown track, pass through

    # Detect unavailable metrics
    unavailable: set[str] = set()
    try:
        import sacrebleu  # noqa: F401
    except ImportError:
        unavailable.add("bleu")
    try:
        from rouge_score import rouge_scorer  # noqa: F401
    except ImportError:
        unavailable.add("rouge_l")

    # embedding_similarity requires litellm and OPENAI_API_KEY
    try:
        import litellm  # noqa: F401
        if not os.getenv("OPENAI_API_KEY"):
            unavailable.add("embedding_similarity")
    except ImportError:
        unavailable.add("embedding_similarity")


    filtered = [m for m in all_metrics if m not in unavailable]

    # If user provided an explicit filter, intersect
    if user_filter:
        filtered = [m for m in filtered if m in user_filter]

    return filtered if filtered else None


# ===========================================================================
# Helpers
# ===========================================================================

def _get_hop_type(metadata: dict[str, Any] | None) -> str:
    """Extract hop type from dataset example metadata."""
    if metadata and "hop_type" in metadata:
        return metadata["hop_type"]
    if metadata and "id" in metadata:
        qid = metadata["id"]
        if "1hop" in qid:
            return "1-hop"
        if "2hop" in qid:
            return "2-hop"
        if "3hop" in qid:
            return "3-hop"
        if "agg" in qid:
            return "aggregation"
        if "oos" in qid:
            return "out-of-scope"
    return "unknown"


def _classify_legitimacy(metric_name: str, judge_mode: str) -> str:
    """
    Returns the legitimacy tag for a metric given the current judge mode.

    - "deterministic" metrics are always legit regardless of judge mode.
    - "judge-scored" metrics are legit only if judge_mode == "live".
    - With dummy judge, judge-scored metrics are tagged "pseudo-random".
    """
    base = METRIC_LEGITIMACY.get(metric_name, "unknown")
    if base == "deterministic":
        return "deterministic"
    if base == "judge-scored":
        return "legit (LLM-judged)" if judge_mode == "live" else "pseudo-random (dummy judge)"
    return "unknown"


def _safe_mean(values: list[float]) -> float:
    """Compute mean, returning 0.0 for empty lists."""
    return sum(values) / len(values) if values else 0.0


# ===========================================================================
# Phase 1: Run all tracks and collect per-example results
# ===========================================================================

def run_all_tracks(
    dataset_path: str,
    adapter_module: str,
    judge_backend: str,
    judge_model: str,
    limit: int | None,
    metrics_filter: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Runs every track in TRACKS against the dataset and returns a merged
    list of per-example result dicts.

    Each result dict has:
        - input, reference, metadata (from dataset)
        - adapter_output, adapter_context, adapter_latency_ms (from adapter)
        - scores: {metric_name: score} merged across all tracks
        - hop_type: extracted from metadata
    """
    # Load dataset examples
    examples = load_dataset(dataset_path)
    if limit and limit > 0:
        examples = examples[:limit]

    print(f"  Dataset loaded: {len(examples)} examples from {dataset_path}")

    # Instantiate adapter
    adapter_cls = registry.resolve_adapter(adapter_module)
    adapter = adapter_cls(use_cache=False)  # disable cache during eval

    # Run adapter on each example once, cache results
    print("  Running adapter on all examples...")
    adapter_results: list[dict[str, Any]] = []
    for i, ex in enumerate(examples, 1):
        t0 = time.time()
        try:
            resp = adapter.run(ex.input, ex.metadata)
            if isinstance(resp, str):
                resp = AdapterResponse(output=resp)
        except Exception as exc:
            print(f"    [WARN] Example {i} adapter error: {exc}")
            resp = AdapterResponse(output=f"[ERROR] {exc}", context=[], latency_ms=0.0)
        elapsed_ms = (time.time() - t0) * 1000

        adapter_results.append({
            "input": ex.input,
            "reference": ex.reference,
            "context_from_dataset": ex.context,
            "metadata": ex.metadata,
            "adapter_output": resp.output,
            "adapter_context": resp.context or [],
            "adapter_latency_ms": resp.latency_ms or elapsed_ms,
            "adapter_metadata": resp.metadata or {},
            "hop_type": _get_hop_type(ex.metadata),
            "scores": {},
        })

        if i % 10 == 0 or i == len(examples):
            print(f"    Adapter: {i}/{len(examples)} examples done")

    # For each track, instantiate evaluator and score
    for track_name in TRACKS:
        print(f"  Running evaluator track: {track_name}")
        evaluator_cls = registry.resolve_evaluator(track_name)
        judge_cls = registry.resolve_judge_backend(judge_backend)
        judge = judge_cls(model=judge_model)

        # Build per-track metrics list, excluding unavailable ones
        track_metrics = _get_track_metrics(track_name, metrics_filter)
        try:
            evaluator = evaluator_cls(judge=judge, metrics=track_metrics)
        except TypeError:
            # Some evaluators don't accept 'judge' kwarg (text_similarity)
            evaluator = evaluator_cls(metrics=track_metrics)

        for i, result in enumerate(adapter_results, 1):
            # Use runtime context from adapter if available, else dataset context
            context = result["adapter_context"] or result.get("context_from_dataset") or []
            try:
                scores = evaluator.evaluate(
                    example_input=result["input"],
                    output=result["adapter_output"],
                    reference=result["reference"],
                    context=context,
                    metadata=result["metadata"],
                )
            except Exception as exc:
                print(f"    [WARN] {track_name} eval error on example {i}: {exc}")
                scores = {}

            # Prefix scores with track name to avoid collisions
            for metric_name, score in scores.items():
                result["scores"][f"{track_name}.{metric_name}"] = score

    return adapter_results


# ===========================================================================
# Phase 2: Aggregate and stratify
# ===========================================================================

def aggregate_results(
    results: list[dict[str, Any]], judge_mode: str
) -> dict[str, Any]:
    """
    Builds a structured aggregate report from per-example results.

    Returns a dict with:
        - overall: {metric: mean_score} across all examples
        - by_hop: {hop_type: {metric: mean_score}}
        - metric_legitimacy: {metric: legitimacy_tag}
        - per_example: list of per-example result dicts
        - summary_stats: total examples, latency stats
    """
    # Collect all metric names
    all_metrics: set[str] = set()
    for r in results:
        all_metrics.update(r["scores"].keys())
    all_metrics_sorted = sorted(all_metrics)

    # Overall aggregation
    overall: dict[str, float] = {}
    for metric in all_metrics_sorted:
        values = [r["scores"][metric] for r in results if metric in r["scores"]]
        overall[metric] = _safe_mean(values)

    # Per-hop aggregation
    by_hop: dict[str, dict[str, float]] = {}
    for hop in HOP_ORDER:
        hop_results = [r for r in results if r["hop_type"] == hop]
        if not hop_results:
            continue
        by_hop[hop] = {}
        for metric in all_metrics_sorted:
            values = [r["scores"][metric] for r in hop_results if metric in r["scores"]]
            by_hop[hop][metric] = _safe_mean(values)

    # Metric legitimacy
    legitimacy: dict[str, str] = {}
    for metric in all_metrics_sorted:
        # Strip track prefix for lookup
        base_metric = metric.split(".", 1)[-1] if "." in metric else metric
        legitimacy[metric] = _classify_legitimacy(base_metric, judge_mode)

    # Latency stats
    latencies = [r["adapter_latency_ms"] for r in results if r["adapter_latency_ms"]]
    latencies_sorted = sorted(latencies) if latencies else [0.0]

    return {
        "overall": overall,
        "by_hop": by_hop,
        "metric_legitimacy": legitimacy,
        "per_example": results,
        "summary_stats": {
            "total_examples": len(results),
            "hop_distribution": {
                hop: len([r for r in results if r["hop_type"] == hop])
                for hop in HOP_ORDER
            },
            "latency_mean_ms": _safe_mean(latencies),
            "latency_p50_ms": latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0.0,
            "latency_p95_ms": latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0.0,
        },
    }


# ===========================================================================
# Phase 3: Generate reports
# ===========================================================================

def generate_json_report(agg: dict[str, Any], output_path: Path) -> None:
    """Writes the full aggregated report as JSON."""
    # Strip per_example adapter_context to reduce file size (can be huge)
    slim = dict(agg)
    slim["per_example"] = [
        {k: v for k, v in ex.items() if k != "adapter_context"}
        for ex in agg["per_example"]
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    print(f"  JSON report written: {output_path}")


def generate_markdown_report(
    agg: dict[str, Any], judge_mode: str, output_path: Path
) -> None:
    """Writes a human-readable Markdown report with stratified tables."""
    lines: list[str] = []
    lines.append("# GraphRAG Full Evaluation Report")
    lines.append("")
    lines.append(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    lines.append(f"**Judge Mode**: `{judge_mode}` {'(scores are real LLM-judged)' if judge_mode == 'live' else '⚠️ (judge-scored metrics are pseudo-random, NOT real quality signals)'}")
    lines.append(f"**Total Examples**: {agg['summary_stats']['total_examples']}")
    lines.append("")

    # Legitimacy legend
    lines.append("## Score Legitimacy Legend")
    lines.append("")
    lines.append("| Tag | Meaning |")
    lines.append("|---|---|")
    lines.append("| ✅ `deterministic` | Algorithmically computed (token overlap, exact match). Always valid. |")
    lines.append("| ✅ `legit (LLM-judged)` | Scored by a real LLM judge. Valid when `--mode live`. |")
    lines.append("| ⚠️ `pseudo-random (dummy judge)` | Hash-derived fake score from DummyJudgeBackend. **NOT a real quality signal.** |")
    lines.append("")

    # Overall scores table
    lines.append("## Overall Scores (All 50 Questions)")
    lines.append("")
    lines.append("| Metric | Score | Legitimacy |")
    lines.append("|---|---|---|")
    for metric, score in sorted(agg["overall"].items()):
        leg = agg["metric_legitimacy"].get(metric, "unknown")
        icon = "✅" if "deterministic" in leg or "legit" in leg else "⚠️"
        lines.append(f"| `{metric}` | {score:.4f} | {icon} {leg} |")
    lines.append("")

    # Per-hop breakdown
    lines.append("## Per-Hop-Type Breakdown")
    lines.append("")
    for hop in HOP_ORDER:
        if hop not in agg["by_hop"]:
            continue
        count = agg["summary_stats"]["hop_distribution"].get(hop, 0)
        lines.append(f"### {hop} ({count} questions)")
        lines.append("")
        lines.append("| Metric | Score | Legitimacy |")
        lines.append("|---|---|---|")
        for metric, score in sorted(agg["by_hop"][hop].items()):
            leg = agg["metric_legitimacy"].get(metric, "unknown")
            icon = "✅" if "deterministic" in leg or "legit" in leg else "⚠️"
            lines.append(f"| `{metric}` | {score:.4f} | {icon} {leg} |")
        lines.append("")

    # Latency summary
    lines.append("## Latency Summary")
    lines.append("")
    stats = agg["summary_stats"]
    lines.append(f"- **Mean**: {stats['latency_mean_ms']:.1f} ms")
    lines.append(f"- **P50**: {stats['latency_p50_ms']:.1f} ms")
    lines.append(f"- **P95**: {stats['latency_p95_ms']:.1f} ms")
    lines.append("")

    # How to verify scores
    lines.append("## How to Verify These Scores")
    lines.append("")
    lines.append("### Deterministic metrics (always valid)")
    lines.append("- `f1`, `exact_match`, `chunk_utilization`, `precision_at_k`, `recall_at_k`, `mrr`")
    lines.append("- These are pure math — token overlap, set intersection, rank reciprocals.")
    lines.append("- **Verification**: Pick any example, manually compute the token F1 between `adapter_output` and `reference`. It will match the reported score exactly.")
    lines.append("")
    lines.append("### Judge-scored metrics (valid only with real LLM judge)")
    lines.append("- `faithfulness`, `context_precision`, `answer_relevancy`, `hallucination_rate`")
    lines.append("- With `--mode dummy`: scores are SHA-256 hash-derived pseudo-random numbers. **Ignore them.**")
    lines.append("- With `--mode live`: an LLM reads the context+answer and scores 0.0–1.0.")
    lines.append("- **Verification**: Run with `--mode live --judge-model gemini/gemini-2.0-flash` (or `gpt-4o-mini`), then compare against manual human judgment on 5–10 spot-check samples.")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Markdown report written: {output_path}")


def generate_spot_checks(
    results: list[dict[str, Any]], count: int, output_path: Path
) -> None:
    """
    Picks N random examples and formats them for human manual verification.
    This is how you verify evalkit scores are legit: read the question,
    reference, system answer, and retrieved context, then compare with
    the computed scores.
    """
    samples = random.sample(results, min(count, len(results)))
    lines: list[str] = []
    lines.append("# Spot-Check Samples for Manual Verification")
    lines.append("")
    lines.append(f"**{len(samples)} randomly selected examples** for human review.")
    lines.append("Compare the system answer and retrieved context against the reference")
    lines.append("to verify whether the computed scores make sense.")
    lines.append("")

    for i, sample in enumerate(samples, 1):
        lines.append(f"## Sample {i}: `{sample.get('metadata', {}).get('id', 'N/A')}` ({sample['hop_type']})")
        lines.append("")
        lines.append(f"**Question**: {sample['input']}")
        lines.append("")
        lines.append(f"**Reference**: {sample['reference']}")
        lines.append("")
        lines.append(f"**System Answer**:")
        lines.append(f"```")
        lines.append(sample["adapter_output"][:500])
        lines.append(f"```")
        lines.append("")

        # Show first 3 context passages
        ctx = sample.get("adapter_context", [])[:3]
        if ctx:
            lines.append(f"**Retrieved Context** (first {len(ctx)} passages):")
            for j, passage in enumerate(ctx, 1):
                lines.append(f"  {j}. {passage[:200]}...")
            lines.append("")

        # Show scores
        lines.append("**Computed Scores**:")
        lines.append("")
        lines.append("| Metric | Score |")
        lines.append("|---|---|")
        for metric, score in sorted(sample["scores"].items()):
            lines.append(f"| `{metric}` | {score:.4f} |")
        lines.append("")
        lines.append("**Manual Check**: Does the system answer address the question?")
        lines.append("Does it contain the expected keywords from the reference?")
        lines.append("Is the F1 score consistent with what you'd expect from the overlap?")
        lines.append("")
        lines.append("---")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Spot-check samples written: {output_path}")


# ===========================================================================
# CLI Entry Point
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run comprehensive GraphRAG evaluation across all evalkit tracks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Offline smoke test (dummy judge, fast, no API calls)
  python scripts/run_full_evaluation.py --mode dummy

  # Full live evaluation with real LLM judge
  python scripts/run_full_evaluation.py --mode live --judge-model gemini/gemini-2.0-flash

  # Quick 5-question subset test
  python scripts/run_full_evaluation.py --mode dummy --limit 5

  # Custom output directory
  python scripts/run_full_evaluation.py --mode dummy --output-dir data/eval_run_001
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["dummy", "live"],
        default="dummy",
        help="Judge mode: 'dummy' for offline (hash-derived pseudo-scores), 'live' for real LLM judge (default: dummy)",
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
        help="LLM model for judge scoring in live mode (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of examples to evaluate (default: all 50)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/full_evaluation",
        help="Output directory for reports (default: data/full_evaluation)",
    )
    parser.add_argument(
        "--dataset",
        default="data/evalkit_dataset.jsonl",
        help="Path to evalkit dataset (default: data/evalkit_dataset.jsonl)",
    )
    parser.add_argument(
        "--spot-checks",
        type=int,
        default=SPOT_CHECK_COUNT,
        help=f"Number of random spot-check samples for manual verification (default: {SPOT_CHECK_COUNT})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for spot-check sampling reproducibility (default: 42)",
    )
    args = parser.parse_args()

    random.seed(args.seed)
    if args.mode == "dummy":
        judge_backend = "dummy"
        judge_model = "dummy"
    else:
        try:
            import litellm  # noqa: F401
            judge_backend = "litellm"
            judge_model = args.judge_model
        except ImportError:
            judge_backend = "openai_compatible"
            judge_model = args.judge_model if args.judge_model != "gpt-4o-mini" else os.getenv("EXTRACTION_MODEL", "nvidia/nemotron-3-super-120b-a12b")

    output_dir = Path(args.output_dir)


    print("=" * 70)
    print("GraphRAG Comprehensive Evaluation")
    print("=" * 70)
    print(f"  Mode         : {args.mode}")
    print(f"  Judge backend: {judge_backend}")
    print(f"  Judge model  : {judge_model}")
    print(f"  Dataset      : {args.dataset}")
    print(f"  Limit        : {args.limit or 'all'}")
    print(f"  Output dir   : {output_dir}")
    print(f"  Tracks       : {', '.join(TRACKS)}")
    print("=" * 70)

    # Determine which metrics to skip based on available libraries
    # Skip bleu/rouge_l if sacrebleu/rouge_score not installed
    # Skip embedding_similarity if no API key for embeddings
    metrics_to_skip: set[str] = set()
    try:
        import sacrebleu  # noqa: F401
    except ImportError:
        metrics_to_skip.add("bleu")
        print("  [INFO] sacrebleu not installed, skipping bleu metric")
    try:
        from rouge_score import rouge_scorer  # noqa: F401
    except ImportError:
        metrics_to_skip.add("rouge_l")
        print("  [INFO] rouge-score not installed, skipping rouge_l metric")

    if args.mode == "dummy":
        metrics_to_skip.add("embedding_similarity")
        print("  [INFO] Dummy mode, skipping embedding_similarity metric")

    # Build metrics filter: None means "all", but we need to exclude unavailable ones
    # We pass None and let evaluators use their defaults; skip filtering is handled
    # by catching ImportErrors in the evaluator
    metrics_filter = None  # let each evaluator use its full default set

    t_start = time.monotonic()

    # Phase 1: Run all tracks
    print("\n[Phase 1] Running adapter + evaluators on all examples...")
    results = run_all_tracks(
        dataset_path=args.dataset,
        adapter_module="eval_adapter:GraphRAGAdapter",
        judge_backend=judge_backend,
        judge_model=judge_model,
        limit=args.limit,
        metrics_filter=metrics_filter,
    )

    # Phase 2: Aggregate
    print("\n[Phase 2] Aggregating and stratifying results...")
    agg = aggregate_results(results, judge_mode=args.mode)

    # Phase 3: Reports
    print("\n[Phase 3] Generating reports...")
    generate_json_report(agg, output_dir / "full_eval_results.json")
    generate_markdown_report(agg, args.mode, output_dir / "full_eval_report.md")
    generate_spot_checks(results, args.spot_checks, output_dir / "spot_check_samples.md")

    t_elapsed = time.monotonic() - t_start
    print(f"\n{'=' * 70}")
    print(f"Evaluation complete in {t_elapsed:.1f}s")
    print(f"{'=' * 70}")

    # Print quick summary to console
    print("\n--- Quick Summary (deterministic metrics only) ---")
    for metric, score in sorted(agg["overall"].items()):
        base = metric.split(".", 1)[-1] if "." in metric else metric
        if METRIC_LEGITIMACY.get(base) == "deterministic":
            print(f"  {metric:<35}: {score:.4f}")

    if args.mode == "dummy":
        print("\n[WARNING] Judge-scored metrics (faithfulness, context_precision, answer_relevancy)")
        print("          are pseudo-random with dummy judge. Run with --mode live for real scores.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
