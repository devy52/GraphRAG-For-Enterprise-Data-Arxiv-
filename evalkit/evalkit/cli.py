from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import evalkit  # noqa: F401  (triggers built-in registration)
from evalkit.core.cache import FileCache
from evalkit.core.config import EvalConfig
from evalkit.core.registry import registry
from evalkit.core.regression import detect_regressions
from evalkit.core.run_store import RunStore
from evalkit.core.runner import EvalResult, Runner

REGRESSION_DISPLAY_LIMIT = 20


def _run_from_config(config_path: str, args: argparse.Namespace | None = None) -> tuple[EvalConfig, EvalResult]:
    config = EvalConfig.from_yaml(config_path)
    if args is not None:
        if getattr(args, "isolated", False):
            config.isolated = True
            config.cache = False
            config.save_run = False
        if getattr(args, "no_cache", False):
            config.cache = False
        if getattr(args, "no_save_run", False):
            config.save_run = False
        if getattr(args, "concurrency", None):
            config.max_concurrency = args.concurrency
    result = Runner(config).run()
    return config, result


def _build_run_info(config: EvalConfig, result: EvalResult) -> dict:
    multi = isinstance(config.track, list)
    track_names = config.track if multi else [config.track]

    metric_descriptions: dict[str, str] = {
        "latency_ms": (
            "Wall-clock time for the adapter call (time.monotonic() around "
            "adapter.run()), in milliseconds. Measures your system's response "
            "time, not judge/evaluator overhead."
        ),
        "cost": "Estimated monetary cost of the LLM generation and judge evaluation calls (USD).",
    }
    for track_name in track_names:
        evaluator_cls = registry.resolve_evaluator(track_name)
        descriptions = getattr(evaluator_cls, "METRIC_DESCRIPTIONS", {})
        if multi:
            metric_descriptions.update({f"{track_name}.{k}": v for k, v in descriptions.items()})
        else:
            metric_descriptions.update(descriptions)

    return {
        "track": ", ".join(track_names) if multi else config.track,
        "dataset": config.dataset,
        "adapter": config.adapter,
        "judge_backend": config.judge_backend,
        "judge_model": config.judge_model,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "thresholds": [{"metric": t.metric, "min": t.min, "max": t.max} for t in config.thresholds],
        "metric_descriptions": metric_descriptions,
        "cache_stats": result.cache_stats,
    }


def _print_regressions(regressions: list[dict], threshold: float) -> None:
    if not regressions:
        print("\nNo per-example regressions found.")
        return
    print(f"\n{len(regressions)} regression(s) found (threshold: {threshold}):")
    for r in regressions[:REGRESSION_DISPLAY_LIMIT]:
        print(f"  [{r['metric']}] {r['before']:.3f} -> {r['after']:.3f}  \"{r['input'][:60]}\"")
    if len(regressions) > REGRESSION_DISPLAY_LIMIT:
        print(f"  ... and {len(regressions) - REGRESSION_DISPLAY_LIMIT} more")


def cmd_run(args: argparse.Namespace) -> int:
    config, result = _run_from_config(args.config, args)
    run_info = _build_run_info(config, result)

    reporter_cls = registry.resolve_reporter(config.reporter)
    try:
        reporter_cls().render(result.per_example, config.output, run_info=run_info)
    except TypeError:
        # A reporter written before run_info existed won't accept the kwarg —
        # fall back so custom reporters never break on this addition.
        reporter_cls().render(result.per_example, config.output)

    print("Aggregate scores:")
    for metric, score in result.aggregate().items():
        print(f"  {metric}: {score:.3f}")
    if result.cache_stats:
        h, m = result.cache_stats["hits"], result.cache_stats["misses"]
        print(f"Cache: {h} hit{'s' if h != 1 else ''}, {m} miss{'es' if m != 1 else ''}")
    print(f"Report written to {config.output}")

    save_run = config.save_run and not getattr(args, "no_save_run", False)
    if save_run:
        run_id = RunStore(config.runs_dir).save(result, run_id=args.run_id)
        print(f"Run saved as: {run_id}  (evalkit diff {run_id} <other_run>)")

    return 0


def cmd_assert(args: argparse.Namespace) -> int:
    config, result = _run_from_config(args.config, args)
    failures = result.failed_thresholds()
    if failures:
        print("FAILED thresholds:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("All thresholds passed.")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    _, result_a = _run_from_config(args.config_a, args)
    _, result_b = _run_from_config(args.config_b, args)
    agg_a, agg_b = result_a.aggregate(), result_b.aggregate()

    metrics = sorted(set(agg_a) | set(agg_b))
    print(f"{'metric':<20}{'A':>10}{'B':>10}{'diff':>10}")
    for m in metrics:
        a, b = agg_a.get(m, 0.0), agg_b.get(m, 0.0)
        print(f"{m:<20}{a:>10.3f}{b:>10.3f}{b - a:>+10.3f}")

    regressions = detect_regressions(
        result_a.per_example, result_b.per_example, threshold=args.regression_threshold
    )
    _print_regressions(regressions, args.regression_threshold)
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    store = RunStore(args.runs_dir)
    run_a = store.load(args.run_a)
    run_b = store.load(args.run_b)

    agg_a, agg_b = run_a["aggregate"], run_b["aggregate"]
    metrics = sorted(set(agg_a) | set(agg_b))
    print(f"Comparing {args.run_a} (A, {run_a['created_at']}) -> {args.run_b} (B, {run_b['created_at']})")
    print(f"{'metric':<20}{'A':>10}{'B':>10}{'diff':>10}")
    for m in metrics:
        a, b = agg_a.get(m, 0.0), agg_b.get(m, 0.0)
        print(f"{m:<20}{a:>10.3f}{b:>10.3f}{b - a:>+10.3f}")

    regressions = detect_regressions(
        run_a["per_example"], run_b["per_example"], threshold=args.regression_threshold
    )
    _print_regressions(regressions, args.regression_threshold)
    return 0


def cmd_runs_list(args: argparse.Namespace) -> int:
    store = RunStore(args.runs_dir)
    runs = store.list_runs()
    if not runs:
        print(f"No runs stored in {args.runs_dir}")
        return 0
    for run_id in runs:
        data = store.load(run_id)
        print(f"{run_id}  ({data['created_at']}, track={data['track']}, dataset={data['dataset']})")
    return 0


def cmd_cache_clear(args: argparse.Namespace) -> int:
    cache = FileCache(args.cache_dir)
    count = cache.clear()
    print(f"Cleared {count} cached entr{'y' if count == 1 else 'ies'} from {args.cache_dir}")
    return 0


def _add_run_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--isolated", action="store_true", dest="isolated", help="Run in complete isolation: disables both caching and run persistence")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache", help="Disable judge-call caching for this run")
    parser.add_argument("--concurrency", type=int, default=None, help="Override max_concurrency from config")


def main() -> None:
    parser = argparse.ArgumentParser(prog="evalkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run an evaluation from a config file")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--run-id", default=None, help="Name this run for later `diff` (default: auto-generated timestamp)")
    p_run.add_argument("--no-save-run", action="store_true", dest="no_save_run", help="Don't persist this run for later diffing")
    _add_run_flags(p_run)
    p_run.set_defaults(func=cmd_run)

    p_assert = sub.add_parser("assert", help="Run and exit non-zero if any threshold fails (for CI)")
    p_assert.add_argument("--config", required=True)
    _add_run_flags(p_assert)
    p_assert.set_defaults(func=cmd_assert)

    p_compare = sub.add_parser("compare", help="Run two configs and diff their aggregate + per-example scores")
    p_compare.add_argument("--config-a", required=True, dest="config_a")
    p_compare.add_argument("--config-b", required=True, dest="config_b")
    p_compare.add_argument("--regression-threshold", type=float, default=0.1, dest="regression_threshold")
    _add_run_flags(p_compare)
    p_compare.set_defaults(func=cmd_compare)

    p_diff = sub.add_parser("diff", help="Compare two previously saved runs without re-running anything")
    p_diff.add_argument("run_a", help="Run ID to use as the baseline (A)")
    p_diff.add_argument("run_b", help="Run ID to compare against the baseline (B)")
    p_diff.add_argument("--runs-dir", default=".evalkit/runs", dest="runs_dir")
    p_diff.add_argument("--regression-threshold", type=float, default=0.1, dest="regression_threshold")
    p_diff.set_defaults(func=cmd_diff)

    p_runs = sub.add_parser("runs", help="Manage saved runs")
    runs_sub = p_runs.add_subparsers(dest="runs_command", required=True)
    p_runs_list = runs_sub.add_parser("list", help="List saved runs")
    p_runs_list.add_argument("--runs-dir", default=".evalkit/runs", dest="runs_dir")
    p_runs_list.set_defaults(func=cmd_runs_list)

    p_cache = sub.add_parser("cache", help="Manage the judge-call cache")
    cache_sub = p_cache.add_subparsers(dest="cache_command", required=True)
    p_cache_clear = cache_sub.add_parser("clear", help="Delete all cached judge scores")
    p_cache_clear.add_argument("--cache-dir", default=".evalkit/cache", dest="cache_dir")
    p_cache_clear.set_defaults(func=cmd_cache_clear)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
