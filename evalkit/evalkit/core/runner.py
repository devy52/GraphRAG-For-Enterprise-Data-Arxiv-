from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from evalkit.contracts.adapter import AdapterResponse
from evalkit.core.cache import CachingJudgeBackend, FileCache
from evalkit.core.config import EvalConfig
from evalkit.core.dataset import EvalExample, load_dataset
from evalkit.core.registry import registry


class EvalResult:
    def __init__(
        self,
        config: EvalConfig,
        per_example: list[dict[str, Any]],
        cache_stats: Optional[dict[str, int]] = None,
    ) -> None:
        self.config = config
        self.per_example = per_example
        self.cache_stats = cache_stats

    def aggregate(self) -> dict[str, float]:
        """Mean of each metric across all examples that reported it."""
        totals: dict[str, list[float]] = {}
        for row in self.per_example:
            for metric, score in row["scores"].items():
                totals.setdefault(metric, []).append(score)
        return {m: sum(v) / len(v) for m, v in totals.items()}

    def failed_thresholds(self) -> list[str]:
        from evalkit.core.stats import failure_rate, percentile

        agg = self.aggregate()
        failures: list[str] = []

        for t in self.config.thresholds:
            values = [
                row["scores"][t.metric] for row in self.per_example if t.metric in row["scores"]
            ]
            if not values:
                failures.append(f"{t.metric}: no scores reported (check track/metrics config)")
                continue

            mean = agg[t.metric]
            if t.min is not None and mean < t.min:
                failures.append(f"{t.metric}: mean {mean:.3f} < {t.min} (min)")
            if t.max is not None and mean > t.max:
                failures.append(f"{t.metric}: mean {mean:.3f} > {t.max} (max)")

            if t.worst_case_min is not None:
                worst = min(values)
                if worst < t.worst_case_min:
                    failures.append(
                        f"{t.metric}: worst-case {worst:.3f} < {t.worst_case_min} (worst_case_min)"
                    )
            if t.worst_case_max is not None:
                worst = max(values)
                if worst > t.worst_case_max:
                    failures.append(
                        f"{t.metric}: worst-case {worst:.3f} > {t.worst_case_max} (worst_case_max)"
                    )

            if t.tail_min is not None:
                worst_tail = percentile(values, t.tail_percentile)
                if worst_tail < t.tail_min:
                    failures.append(
                        f"{t.metric}: worst {t.tail_percentile:g}% (p{t.tail_percentile:g}) "
                        f"{worst_tail:.3f} < {t.tail_min} (tail_min)"
                    )
            if t.tail_max is not None:
                worst_tail = percentile(values, 100 - t.tail_percentile)
                if worst_tail > t.tail_max:
                    failures.append(
                        f"{t.metric}: worst {t.tail_percentile:g}% (p{100 - t.tail_percentile:g}) "
                        f"{worst_tail:.3f} > {t.tail_max} (tail_max)"
                    )

            if t.max_failure_rate is not None:
                rate = failure_rate(values, t.failure_below)
                if rate > t.max_failure_rate:
                    failures.append(
                        f"{t.metric}: failure rate {rate:.1%} > {t.max_failure_rate:.1%} "
                        f"(examples scoring below {t.failure_below})"
                    )

        return failures


class Runner:
    """Track-agnostic core engine. Knows nothing about RAG, codegen, or any
    specific track — it just wires together whatever adapter, evaluator(s),
    and judge backend the config points at, built-in or user-supplied.

    `track` can be a single evaluator or a list — a list runs every
    evaluator in it against the same dataset and merges their scores into
    one report, so you get every metric every configured evaluator can
    produce, not just one evaluator's view.

    `max_concurrency` > 1 processes examples in parallel via a thread pool.
    This deliberately does NOT require BaseEvaluator/BaseAdapter/
    BaseJudgeBackend to become async — sync I/O (HTTP calls to a judge
    model or your adapter's endpoint) releases the GIL while waiting, so
    thread-based concurrency gets real parallelism without changing any
    contract. Result order always matches dataset order regardless of
    concurrency, since results can otherwise complete out of order.
    """

    def __init__(self, config: EvalConfig) -> None:
        self.config = config

    def run(self) -> EvalResult:
        examples = load_dataset(self.config.dataset)

        adapter_cls = registry.resolve_adapter(self.config.adapter)
        adapter = adapter_cls(**self.config.adapter_config)

        judge_backend_cls = registry.resolve_judge_backend(self.config.judge_backend)
        judge = judge_backend_cls(model=self.config.judge_model, **self.config.judge_config)
        if self.config.cache:
            judge = CachingJudgeBackend(
                judge, FileCache(self.config.cache_dir), model=self.config.judge_model
            )

        multi = isinstance(self.config.track, list)
        track_names = self.config.track if multi else [self.config.track]

        RESERVED_EVALUATOR_KWARGS = {"judge", "metrics"}

        evaluators: list[tuple[str, Any]] = []
        for track_name in track_names:
            evaluator_cls = registry.resolve_evaluator(track_name)
            if multi:
                # Nested form: {"ragas": {"ragas_model": "..."}, ...}. A
                # track with no special config just omits its key.
                extra_kwargs = self.config.evaluator_config.get(track_name, {})
            else:
                extra_kwargs = self.config.evaluator_config
            collision = RESERVED_EVALUATOR_KWARGS & extra_kwargs.keys()
            if collision:
                raise ValueError(
                    f"evaluator_config for '{track_name}' sets {sorted(collision)}, "
                    "which are already configured via the top-level 'metrics' and "
                    "'judge_backend'/'judge_model' fields — remove them from evaluator_config."
                )
            evaluator = evaluator_cls(
                judge=judge, metrics=self.config.metrics or None, **extra_kwargs
            )
            evaluators.append((track_name, evaluator))

        def process_one(example: EvalExample) -> dict[str, Any]:
            started = time.monotonic()
            raw_response = adapter.run(example.input, example.metadata)
            adapter_wall_latency_ms = (time.monotonic() - started) * 1000

            if isinstance(raw_response, AdapterResponse):
                response = raw_response
                output = response.output
                eval_context = response.context if response.context is not None else example.context
                latency_ms = (
                    response.latency_ms
                    if response.latency_ms is not None
                    else adapter_wall_latency_ms
                )
                response_metadata = response.metadata or {}
            elif isinstance(raw_response, str):
                response = AdapterResponse(output=raw_response)
                output = response.output
                eval_context = example.context
                latency_ms = adapter_wall_latency_ms
                response_metadata = {}
            else:
                raise TypeError(
                    "BaseAdapter.run() must return a str or AdapterResponse, "
                    f"got {type(raw_response).__name__}"
                )

            combined_metadata = dict(example.metadata)
            combined_metadata.update(response_metadata)

            # Compute or extract dollar cost
            cost = 0.0
            if "cost" in combined_metadata:
                cost = float(combined_metadata["cost"])
            elif "prompt_tokens" in combined_metadata or "completion_tokens" in combined_metadata:
                p_tok = float(combined_metadata.get("prompt_tokens", 0))
                c_tok = float(combined_metadata.get("completion_tokens", 0))
                cost = (p_tok * 0.00000015) + (c_tok * 0.00000060)
            elif "tokens" in combined_metadata:
                cost = float(combined_metadata["tokens"]) * 0.00000020

            combined_scores: dict[str, float] = {
                "latency_ms": latency_ms,
                "cost": cost,
            }
            for track_name, evaluator in evaluators:
                raw_scores = evaluator.evaluate(
                    example_input=example.input,
                    output=output,
                    reference=example.reference,
                    context=eval_context,
                    metadata=combined_metadata,
                )
                if multi:
                    combined_scores.update({f"{track_name}.{k}": v for k, v in raw_scores.items()})
                else:
                    combined_scores.update(raw_scores)

            return {
                "id": example.id,
                "input": example.input,
                "output": output,
                "reference": example.reference,
                "context": eval_context,
                "scores": combined_scores,
                "metadata": combined_metadata,
            }

        if self.config.max_concurrency > 1:
            with ThreadPoolExecutor(max_workers=self.config.max_concurrency) as executor:
                rows = list(executor.map(process_one, examples))
        else:
            rows = [process_one(example) for example in examples]

        cache_stats = None
        if isinstance(judge, CachingJudgeBackend):
            cache_stats = {"hits": judge.hits, "misses": judge.misses}

        return EvalResult(self.config, rows, cache_stats=cache_stats)
