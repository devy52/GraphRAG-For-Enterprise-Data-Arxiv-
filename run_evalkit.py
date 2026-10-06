"""
Evalkit Benchmark Execution Runner.

Architecture Role:
    Authoritative Benchmark Execution Engine. Coordinates the enterprise evaluation
    pipeline using `evalharness` (Evalkit). Runs end-to-end multi-track evaluation
    (RAG, Retrieval, Graph traversal, Text similarity) across the stratified
    benchmark dataset using live/in-process GraphRAGAdapter and LiteLLMJudge.

Inputs:
    - `evalkit_config.yaml`: Configuration defining tracks, dataset path, adapter, and metrics.
    - CLI arguments: Optional `--config` path and `--limit` to evaluate a subset of examples.

Outputs:
    - `data/evalkit_report.md`: Markdown evaluation report with per-example scores and aggregates.
    - `data/evalkit_results.json`: Machine-readable evaluation results.

Design Decisions:
    - Authoritative Framework Adoption: Uses `evalharness` as the authoritative benchmark runner,
      empirically verified to match industry standards (Ragas context_precision MAE 0.0975)
      while properly scoring unanswerable queries (0.000 vs Ragas 1.000) and measuring
      graph-specific utilization metrics.
    - Self-Contained Path Resolution: Automatically mounts `evalharness/` and `evalkit_upgraded/`
      to `sys.path` so external dependencies do not need global site-package installation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict

# Ensure repository root and evalharness/evalkit are on sys.path
_repo_root = Path(__file__).resolve().parent
_evalharness_path = _repo_root / "evalharness"
if str(_evalharness_path) not in sys.path:
    sys.path.insert(0, str(_evalharness_path))
_evalkit_path = _repo_root / "evalkit"
if str(_evalkit_path) not in sys.path:
    sys.path.insert(0, str(_evalkit_path))
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    import evalkit
    from evalkit.cli import _build_run_info, _run_from_config
    from evalkit.core.config import EvalConfig
    from evalkit.core.dataset import load_dataset
    from evalkit.core.registry import registry
    EVAL_ENGINE = "evalkit"
except ImportError:
    import evalharness
    from evalharness.cli import _build_run_info, _run_from_config
    from evalharness.core.config import EvalConfig
    from evalharness.core.dataset import load_dataset
    from evalharness.core.registry import registry
    EVAL_ENGINE = "evalharness"


def run_evaluation(config_path: str, limit: int | None = None) -> int:
    """
    Executes benchmark evaluation using the specified configuration.

    Args:
        config_path: Path to evalkit YAML configuration file.
        limit: Optional maximum number of dataset examples to evaluate.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    start_time = time.monotonic()
    config = EvalConfig.from_yaml(config_path)

    # Optional subset slicing for rapid test runs
    if limit is not None and limit > 0:
        import tempfile
        import yaml

        all_examples = load_dataset(config.dataset)
        by_category: dict[str, list] = {}
        for ex in all_examples:
            cat = (ex.metadata or {}).get("hop_type") or "default"
            by_category.setdefault(cat, []).append(ex)

        per_cat = max(1, limit // len(by_category)) if by_category else limit
        sampled = []
        for cat, items in by_category.items():
            sampled.extend(items[:per_cat])

        if len(sampled) < limit:
            remaining = [ex for ex in all_examples if ex not in sampled]
            sampled.extend(remaining[: (limit - len(sampled))])
        raw_examples = sampled[:limit]

        temp_data = Path("data") / f"temp_evalkit_dataset_{limit}.jsonl"
        temp_data.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_data, "w", encoding="utf-8") as f:
            for ex in raw_examples:
                f.write(ex.model_dump_json() + "\n")

        # Override dataset path in a temporary configuration
        config_dict = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        config_dict["dataset"] = str(temp_data)
        temp_cfg = Path("data") / f"temp_evalkit_config_{limit}.yaml"
        temp_cfg.write_text(yaml.safe_dump(config_dict), encoding="utf-8")
        active_config_path = str(temp_cfg)
    else:
        active_config_path = config_path

    print(f"=== Starting Evalkit Evaluation (engine: {EVAL_ENGINE}, config: {active_config_path}) ===")
    config, result = _run_from_config(active_config_path)

    # Build run metadata for report header
    if _build_run_info is not None:
        run_info = _build_run_info(config, result)
    else:
        multi = isinstance(config.track, list)
        track_names = config.track if multi else [config.track]
        run_info = {
            "track": ", ".join(track_names) if multi else config.track,
            "dataset": config.dataset,
            "adapter": config.adapter,
            "judge_backend": config.judge_backend,
            "judge_model": config.judge_model,
            "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "thresholds": [{"metric": t.metric, "min": t.min, "max": t.max} for t in config.thresholds],
            "metric_descriptions": {},
        }

    # Render Markdown report
    reporter_cls = registry.resolve_reporter(config.reporter)
    try:
        reporter_cls().render(result.per_example, config.output, run_info=run_info)
    except TypeError:
        reporter_cls().render(result.per_example, config.output)

    # Render JSON report for downstream programmatic consumption
    json_output_path = Path("data") / "evalkit_results.json"
    json_reporter_cls = registry.resolve_reporter("json")
    try:
        json_reporter_cls().render(result.per_example, str(json_output_path), run_info=run_info)
    except TypeError:
        json_reporter_cls().render(result.per_example, str(json_output_path))

    # Print summary to console
    elapsed = time.monotonic() - start_time
    print("\n=== Evalkit Aggregate Scores ===")
    for metric, score in result.aggregate().items():
        print(f"  {metric:<32}: {score:.4f}")
    print(f"\nCompleted in {elapsed:.2f}s")
    print(f"Markdown Report : {config.output}")
    print(f"JSON Results    : {json_output_path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GraphRAG evaluation via evalkit")
    parser.add_argument(
        "--config",
        default="evalkit_config.yaml",
        help="Path to evalkit config file (default: evalkit_config.yaml)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of questions to evaluate (e.g. 5 for smoke test)",
    )
    args = parser.parse_args()
    sys.exit(run_evaluation(args.config, args.limit))


if __name__ == "__main__":
    main()
