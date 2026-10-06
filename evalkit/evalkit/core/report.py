from __future__ import annotations

import json
from html import escape
from typing import Any, Optional

from evalkit.contracts.reporter import BaseReporter

PASS_THRESHOLD = 0.7  # used for pass/fail color coding and markers in html and markdown reports

# Metrics that aren't 0.0-1.0 quality scores — raw measurements that need
# different formatting and no pass/fail coloring against PASS_THRESHOLD.
_RAW_VALUE_METRICS = {"latency_ms", "cost"}


def _format_metric_value(name: str, value: float) -> str:
    if name == "latency_ms":
        return f"{value:.1f}ms"
    if name == "cost":
        return f"${value:.6f}"
    return f"{value:.3f}"



class JSONReporter(BaseReporter):
    def render(
        self,
        results: list[dict[str, Any]],
        output_path: str,
        run_info: Optional[dict[str, Any]] = None,
    ) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)


_HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>evalkit report</title>
<style>
body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 2rem; background: #0b0e14; color: #e6e6e6; }}
h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
.count {{ color: #8b93a7; font-size: 0.85rem; margin-bottom: 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #2a2f3a; padding: 8px 12px; text-align: left; vertical-align: top; font-size: 0.85rem; }}
th {{ background: #161b26; position: sticky; top: 0; }}
.pass {{ color: #4ade80; }}
.fail {{ color: #f87171; }}
.summary {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
.metric {{ background: #161b26; padding: 0.75rem 1.25rem; border-radius: 8px; }}
.metric .label {{ color: #8b93a7; font-size: 0.8rem; }}
.metric .val {{ font-size: 1.3rem; font-weight: 600; }}
</style></head>
<body>
<h1>evalkit report</h1>
<div class="count">{n} examples · {n_metrics} metric(s)</div>
<div class="summary">{summary_html}</div>
<table>
<tr><th>Input</th><th>Output</th>{metric_headers}</tr>
{rows_html}
</table>
</body></html>"""


class HTMLReporter(BaseReporter):
    """Self-contained single-file HTML report — compact visual summary,
    truncated cells, good for a quick glance or a README screenshot. For a
    full write-up (methodology, untruncated per-example detail), use the
    markdown reporter instead."""

    def render(
        self,
        results: list[dict[str, Any]],
        output_path: str,
        run_info: Optional[dict[str, Any]] = None,
    ) -> None:
        metric_names = sorted({m for r in results for m in r["scores"]})

        summary: dict[str, float] = {}
        for m in metric_names:
            values = [r["scores"][m] for r in results if m in r["scores"]]
            summary[m] = sum(values) / len(values) if values else 0.0

        summary_html = "".join(
            f'<div class="metric"><div class="label">{escape(m)}</div>'
            f'<div class="val">{_format_metric_value(m, v)}</div></div>'
            for m, v in summary.items()
        )
        metric_headers = "".join(f"<th>{escape(m)}</th>" for m in metric_names)

        rows_html_parts = []
        for r in results:
            cells = []
            for m in metric_names:
                if m in r["scores"]:
                    score = r["scores"][m]
                    if m in _RAW_VALUE_METRICS:
                        cells.append(f"<td>{_format_metric_value(m, score)}</td>")
                    else:
                        css = "pass" if score >= PASS_THRESHOLD else "fail"
                        cells.append(f'<td class="{css}">{score:.2f}</td>')
                else:
                    cells.append("<td>-</td>")
            rows_html_parts.append(
                f"<tr><td>{escape(str(r['input'])[:200])}</td>"
                f"<td>{escape(str(r['output'])[:200])}</td>{''.join(cells)}</tr>"
            )

        html = _HTML_TEMPLATE.format(
            n=len(results),
            n_metrics=len(metric_names),
            summary_html=summary_html,
            metric_headers=metric_headers,
            rows_html="\n".join(rows_html_parts),
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)


def _fence(text: str) -> str:
    """Wrap text in a markdown code fence long enough that it can't be
    broken by backtick runs already inside the text itself."""
    longest_run = 0
    current = 0
    for ch in str(text):
        if ch == "`":
            current += 1
            longest_run = max(longest_run, current)
        else:
            current = 0
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}\n{text}\n{fence}"


class MarkdownReporter(BaseReporter):
    """Full-length, git-diffable Markdown report: run metadata, a summary
    table, a methodology section explaining how each metric is computed,
    and the complete (untruncated) per-example breakdown — input, output,
    reference, retrieved context, and scores. Meant to be read as
    documentation and reviewed/diffed in a PR, not just glanced at. This
    is evalkit's default reporter."""

    def render(
        self,
        results: list[dict[str, Any]],
        output_path: str,
        run_info: Optional[dict[str, Any]] = None,
    ) -> None:
        run_info = run_info or {}
        lines: list[str] = []

        lines.append("# evalkit report")
        lines.append("")

        track = run_info.get("track", "unknown")
        dataset = run_info.get("dataset", "unknown")
        adapter = run_info.get("adapter", "unknown")
        judge_backend = run_info.get("judge_backend", "unknown")
        judge_model = run_info.get("judge_model", "unknown")
        generated_at = run_info.get("generated_at")

        if generated_at:
            lines.append(f"- **Generated:** {generated_at}")
        lines.append(f"- **Track:** `{track}`")
        n = len(results)
        lines.append(f"- **Dataset:** `{dataset}` ({n} example{'s' if n != 1 else ''})")
        lines.append(f"- **Adapter:** `{adapter}`")
        lines.append(f"- **Judge backend:** `{judge_backend}` (model: `{judge_model}`)")
        cache_stats = run_info.get("cache_stats")
        if cache_stats:
            lines.append(
                f"- **Cache:** {cache_stats['hits']} hit(s), {cache_stats['misses']} miss(es)"
            )
        lines.append("")

        if judge_backend == "dummy":
            lines.append(
                "> ⚠️ **Scores below are not meaningful.** The `dummy` judge backend "
                "produces a deterministic pseudo-score for exercising the pipeline "
                "offline — it does not evaluate quality. Switch to `judge_backend: "
                "litellm` (or another real backend) for actual scores."
            )
            lines.append("")

        metric_names = sorted({m for r in results for m in r["scores"]})
        summary: dict[str, float] = {}
        for m in metric_names:
            values = [r["scores"][m] for r in results if m in r["scores"]]
            summary[m] = sum(values) / len(values) if values else 0.0

        thresholds_by_metric = {
            t["metric"]: t for t in run_info.get("thresholds", []) if t.get("min") is not None or t.get("max") is not None
        }

        lines.append("## Summary")
        lines.append("")
        if thresholds_by_metric:
            lines.append("| Metric | Average | Threshold | Status |")
            lines.append("|---|---|---|---|")
            for m in metric_names:
                avg = summary[m]
                value_str = _format_metric_value(m, avg)
                if m in thresholds_by_metric:
                    t = thresholds_by_metric[m]
                    min_val, max_val = t.get("min"), t.get("max")
                    passed = (min_val is None or avg >= min_val) and (max_val is None or avg <= max_val)
                    status = "✅ Pass" if passed else "❌ Fail"
                    bound = "; ".join(
                        p
                        for p in (
                            f"≥ {min_val}" if min_val is not None else None,
                            f"≤ {max_val}" if max_val is not None else None,
                        )
                        if p
                    )
                    lines.append(f"| {m} | {value_str} | {bound} | {status} |")
                else:
                    lines.append(f"| {m} | {value_str} | — | — |")
        else:
            lines.append("| Metric | Average |")
            lines.append("|---|---|")
            for m in metric_names:
                lines.append(f"| {m} | {_format_metric_value(m, summary[m])} |")
        lines.append("")

        descriptions = run_info.get("metric_descriptions", {})
        if metric_names:
            lines.append("## Methodology")
            lines.append("")
            present_raw_metrics = sorted(_RAW_VALUE_METRICS & set(metric_names))
            if present_raw_metrics:
                lines.append(
                    f"Track `{track}`. Each metric is scored on a 0.0-1.0 scale "
                    f"({PASS_THRESHOLD} used as the pass/fail marker below), "
                    f"except raw measurements ({', '.join(present_raw_metrics)}), "
                    f"which show their actual unit and have no pass/fail marker here — "
                    f"gate those with an explicit `max` threshold instead."
                )
            else:
                lines.append(
                    f"Track `{track}`. Each metric is scored on a 0.0-1.0 scale "
                    f"({PASS_THRESHOLD} used as the pass/fail marker below)."
                )
            lines.append("")
            for m in metric_names:
                desc = descriptions.get(m, "No description provided by this evaluator.")
                lines.append(f"- **{m}**: {desc}")
            lines.append("")

        lines.append("## Per-example results")
        lines.append("")
        for i, r in enumerate(results, start=1):
            lines.append(f"### Example {i}")
            lines.append("")

            lines.append("**Input:**")
            lines.append("")
            lines.append(_fence(r["input"]))
            lines.append("")

            lines.append("**Output:**")
            lines.append("")
            lines.append(_fence(r["output"]))
            lines.append("")

            if r.get("reference"):
                lines.append("**Reference:**")
                lines.append("")
                lines.append(_fence(r["reference"]))
                lines.append("")

            context = r.get("context")
            if context:
                lines.append("**Retrieved context:**")
                lines.append("")
                for c in context:
                    lines.append(_fence(c))
                    lines.append("")

            lines.append("**Scores:**")
            lines.append("")
            lines.append("| Metric | Score |")
            lines.append("|---|---|")
            for m in metric_names:
                if m in r["scores"]:
                    score = r["scores"][m]
                    value_str = _format_metric_value(m, score)
                    if m in _RAW_VALUE_METRICS:
                        lines.append(f"| {m} | {value_str} |")
                    else:
                        marker = "✅" if score >= PASS_THRESHOLD else "❌"
                        lines.append(f"| {m} | {value_str} {marker} |")
                else:
                    lines.append(f"| {m} | — |")
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
