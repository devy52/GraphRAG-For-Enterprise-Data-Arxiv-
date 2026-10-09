from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, Field, model_validator


class ThresholdConfig(BaseModel):
    """A CI gate on one metric. `min`/`max` gate the mean, which is what
    every threshold did before this — kept exactly as-is for backward
    compatibility. The rest are additive: use them when a single
    catastrophic outlier hiding inside a passing average is the actual
    risk, which is common enough that mean-only gating is usually not
    sufficient on its own for anything safety- or quality-critical.
    """

    metric: str

    # Gates the mean — unchanged from earlier versions.
    min: Optional[float] = None
    max: Optional[float] = None

    # Gates the single worst example — the strictest gate: "not even one
    # example may score below/above this," regardless of how good the
    # average looks.
    worst_case_min: Optional[float] = None
    worst_case_max: Optional[float] = None

    # Gates the worst tail of the distribution — the standard SLA-style
    # gate for latency ("95% of requests under Xms" = tail_max with
    # tail_percentile=5, i.e. the top 5% must stay under the bound), but
    # works for any metric. tail_min checks the BOTTOM tail_percentile%
    # (the worst-performing examples for a higher-is-better metric);
    # tail_max checks the TOP tail_percentile% (the worst-performing
    # examples for a lower-is-better metric like latency). This asymmetry
    # is intentional: "the tail" always means "the worst-scoring end,"
    # which is a different end of the sorted distribution depending on
    # which direction is bad for that metric.
    tail_percentile: float = 5.0
    tail_min: Optional[float] = None
    tail_max: Optional[float] = None

    # Gates what fraction of examples count as "failing" — an example
    # fails this metric if its score is below `failure_below`.
    # max_failure_rate requires failure_below (and vice versa).
    max_failure_rate: Optional[float] = None
    failure_below: Optional[float] = None

    @model_validator(mode="after")
    def _validate(self) -> "ThresholdConfig":
        if (self.max_failure_rate is None) != (self.failure_below is None):
            raise ValueError(
                f"threshold for '{self.metric}': max_failure_rate and failure_below "
                "must be set together — failure_below defines what counts as a failing example"
            )
        gates = (
            self.min,
            self.max,
            self.worst_case_min,
            self.worst_case_max,
            self.tail_min,
            self.tail_max,
            self.max_failure_rate,
        )
        if all(g is None for g in gates):
            raise ValueError(
                f"threshold for '{self.metric}' sets no gate at all — it would never fail"
            )
        return self


class EvalConfig(BaseModel):
    """One evaluation run. `track` and `adapter` each accept either a
    built-in name ("rag", "generic", "static") or a dotted path to your own
    class ("mypackage.myeval:MyEvaluator").

    `track` also accepts a list ("[rag, ragas]") to run every evaluator in
    the list against the same dataset in one pass — scores from each are
    merged into one report, metric keys prefixed with the track name
    ("rag.faithfulness", "ragas.faithfulness") so nothing collides. This is
    how you get every possible metric for a project instead of picking one
    evaluator's view of it.
    """

    track: Union[str, list[str]]
    dataset: str
    adapter: str
    adapter_config: dict[str, Any] = Field(default_factory=dict)

    # Extra kwargs passed to the evaluator's constructor beyond judge/metrics.
    # Single-track: flat kwargs, e.g. {"ragas_model": "gpt-4o-mini"}.
    # Multi-track (track is a list): keyed by track name, e.g.
    # {"ragas": {"ragas_model": "gpt-4o-mini"}} — "rag" needs none, so it's
    # simply omitted.
    evaluator_config: dict[str, Any] = Field(default_factory=dict)

    # Subset of metrics each chosen evaluator should compute. Empty = every
    # metric that evaluator supports — this is the "all metrics" default,
    # not something you have to opt into. In multi-track mode this filter
    # applies independently to each evaluator.
    metrics: list[str] = Field(default_factory=list)

    judge_backend: str = "litellm"
    judge_model: str = "gpt-4o-mini"
    judge_config: dict[str, Any] = Field(default_factory=dict)

    # Judge calls (litellm backend only — ragas manages its own calls and
    # isn't affected) are cached by default: same backend+model+prompt ->
    # no repeat API call. Disable with cache: false or --no-cache.
    cache: bool = True
    cache_dir: str = ".evalkit/cache"

    # How many examples to process in parallel. 1 = fully sequential (the
    # original, still-default behavior) — no evaluator/adapter contract
    # changes required to raise this, since sync I/O releases the GIL while
    # waiting on a network call.
    max_concurrency: int = 1

    # Every run is saved as a plain JSON file by default, so it can be
    # compared later with `evalkit diff` without re-executing anything.
    save_run: bool = True
    runs_dir: str = ".evalkit/runs"

    # Single-parameter execution isolation: when true, disables both judge caching
    # and historical run persistence.
    isolated: bool = False

    reporter: str = "markdown"
    output: str = "report.md"

    thresholds: list[ThresholdConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _apply_isolation(self) -> "EvalConfig":
        if self.isolated:
            self.cache = False
            self.save_run = False
        return self

    @classmethod
    def from_yaml(cls, path: str) -> "EvalConfig":
        import yaml

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(**raw)
