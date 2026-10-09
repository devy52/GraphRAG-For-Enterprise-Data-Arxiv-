from __future__ import annotations

import json

from evalkit.core.report import HTMLReporter, JSONReporter, MarkdownReporter, PASS_THRESHOLD, _fence


def test_html_reporter_escapes_malicious_input(tmp_path):
    """Model outputs are untrusted text and get embedded in the HTML report.
    If a RAG system's output (or a prompt-injected retrieval chunk) contains
    a script tag, it must not survive into raw HTML."""
    malicious = "<script>alert('pwned')</script>"
    results = [{"input": malicious, "output": malicious, "scores": {"quality": 0.5}}]

    output_path = tmp_path / "report.html"
    HTMLReporter().render(results, str(output_path))
    html = output_path.read_text(encoding='utf-8')

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_reporter_pass_fail_boundary(tmp_path):
    results = [
        {"input": "a", "output": "a", "scores": {"m": PASS_THRESHOLD}},       # exactly at threshold
        {"input": "b", "output": "b", "scores": {"m": PASS_THRESHOLD - 0.01}},  # just under
    ]
    output_path = tmp_path / "report.html"
    HTMLReporter().render(results, str(output_path))
    html = output_path.read_text(encoding='utf-8')

    assert html.count('class="pass"') == 1
    assert html.count('class="fail"') == 1


def test_html_reporter_handles_missing_metric_gracefully(tmp_path):
    """Not every evaluator computes every metric for every example — the
    report must not crash or mislabel a missing score as a failing one."""
    results = [
        {"input": "a", "output": "a", "scores": {"m1": 0.9}},
        {"input": "b", "output": "b", "scores": {"m2": 0.9}},  # doesn't have m1
    ]
    output_path = tmp_path / "report.html"
    HTMLReporter().render(results, str(output_path))
    html = output_path.read_text(encoding='utf-8')
    assert "<td>-</td>" in html


def test_html_reporter_handles_empty_results(tmp_path):
    output_path = tmp_path / "report.html"
    HTMLReporter().render([], str(output_path))
    assert output_path.exists()
    assert "0 examples" in output_path.read_text(encoding='utf-8')


def test_html_reporter_latency_has_no_false_pass_fail_marker(tmp_path):
    """latency_ms is a raw millisecond value, not a 0-1 score — a fast
    latency (e.g. 5ms) must not render with the 'fail' class just because
    5 < PASS_THRESHOLD (0.7)."""
    results = [{"input": "a", "output": "a", "scores": {"latency_ms": 5.2}}]
    output_path = tmp_path / "report.html"
    HTMLReporter().render(results, str(output_path))
    html = output_path.read_text(encoding='utf-8')
    assert 'class="fail"' not in html
    assert 'class="pass"' not in html
    assert "5.2ms" in html


def test_json_reporter_round_trips(tmp_path):
    results = [{"input": "a", "output": "b", "scores": {"m": 0.5}}]
    output_path = tmp_path / "report.json"
    JSONReporter().render(results, str(output_path))
    assert json.loads(output_path.read_text(encoding='utf-8')) == results


# -- MarkdownReporter --------------------------------------------------------


def test_fence_uses_longer_fence_than_content_backticks():
    assert _fence("plain text").startswith("```\n")

    # content already has a triple-backtick run: fence must be longer or it
    # would prematurely close
    tricky = "here is some ```code``` inline"
    fenced = _fence(tricky)
    opening = fenced.split("\n", 1)[0]
    assert opening == "````"  # one longer than the 3-backtick run inside
    assert tricky in fenced


def test_markdown_reporter_writes_title_and_summary(tmp_path):
    results = [{"input": "q1", "output": "a1", "reference": None, "context": None, "scores": {"quality": 0.8}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')

    assert content.startswith("# evalkit report")
    assert "## Summary" in content
    assert "| quality | 0.800 |" in content


def test_markdown_reporter_includes_run_metadata(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    run_info = {
        "track": "rag",
        "dataset": "data.jsonl",
        "adapter": "static",
        "judge_backend": "litellm",
        "judge_model": "gpt-4o-mini",
        "generated_at": "2026-08-26 12:00 UTC",
    }
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')

    assert "`rag`" in content
    assert "`data.jsonl`" in content
    assert "`static`" in content
    assert "`litellm`" in content
    assert "`gpt-4o-mini`" in content
    assert "2026-08-26 12:00 UTC" in content


def test_markdown_reporter_shows_cache_stats_when_present(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    run_info = {"cache_stats": {"hits": 3, "misses": 7}}
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')
    assert "3 hit(s), 7 miss(es)" in content


def test_markdown_reporter_omits_cache_line_when_absent(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')
    assert "**Cache:**" not in content


def test_markdown_reporter_warns_when_dummy_judge_used(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info={"judge_backend": "dummy"})
    content = output_path.read_text(encoding='utf-8')
    assert "not meaningful" in content.lower()


def test_markdown_reporter_omits_dummy_warning_for_real_judge(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info={"judge_backend": "litellm"})
    content = output_path.read_text(encoding='utf-8')
    assert "not meaningful" not in content.lower()


def test_markdown_reporter_shows_threshold_pass_fail_in_summary(tmp_path):
    results = [
        {"input": "q1", "output": "a1", "reference": None, "context": None, "scores": {"faithfulness": 0.9}},
        {"input": "q2", "output": "a2", "reference": None, "context": None, "scores": {"faithfulness": 0.3}},
    ]
    run_info = {"thresholds": [{"metric": "faithfulness", "min": 0.8}]}
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')

    # average of 0.9 and 0.3 is 0.6, below the 0.8 threshold
    assert "❌ Fail" in content
    assert "≥ 0.8" in content


def test_markdown_reporter_summary_row_with_no_threshold_when_others_have_one(tmp_path):
    """When some metrics have a configured threshold and others don't, the
    ones without one must show the '—' placeholder row, not be skipped or
    crash formatting the threshold column."""
    results = [
        {
            "input": "q",
            "output": "a",
            "reference": None,
            "context": None,
            "scores": {"faithfulness": 0.9, "answer_relevancy": 0.5},
        }
    ]
    run_info = {"thresholds": [{"metric": "faithfulness", "min": 0.8}]}
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')
    assert "| answer_relevancy | 0.500 | — | — |" in content


def test_markdown_reporter_per_example_missing_metric_cell(tmp_path):
    """Not every example necessarily reports every metric (e.g. metrics
    differ per row) — must render a placeholder, not crash or misalign."""
    results = [
        {"input": "q1", "output": "a1", "reference": None, "context": None, "scores": {"m1": 0.9}},
        {"input": "q2", "output": "a2", "reference": None, "context": None, "scores": {"m2": 0.5}},
    ]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')
    assert "| m1 | — |" in content or "| m2 | — |" in content


def test_markdown_reporter_includes_methodology_descriptions(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"faithfulness": 0.5}}]
    run_info = {
        "track": "rag",
        "metric_descriptions": {"faithfulness": "Checks claims against context."},
    }
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')

    assert "## Methodology" in content
    assert "Checks claims against context." in content


def test_markdown_reporter_shows_context_and_reference_when_present(tmp_path):
    results = [
        {
            "input": "When was it built?",
            "output": "1889.",
            "reference": "It was built in 1889.",
            "context": ["Completed in 1889."],
            "scores": {"faithfulness": 0.9},
        }
    ]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')

    assert "**Reference:**" in content
    assert "**Retrieved context:**" in content
    assert "It was built in 1889." in content
    assert "Completed in 1889." in content


def test_markdown_reporter_omits_reference_and_context_sections_when_absent(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": 0.5}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')

    assert "**Reference:**" not in content
    assert "**Retrieved context:**" not in content


def test_markdown_reporter_per_example_score_markers(tmp_path):
    results = [
        {"input": "q", "output": "a", "reference": None, "context": None, "scores": {"m": PASS_THRESHOLD}},
        {"input": "q2", "output": "a2", "reference": None, "context": None, "scores": {"m": PASS_THRESHOLD - 0.1}},
    ]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')

    assert content.count("✅") >= 1
    assert content.count("❌") >= 1


def test_markdown_reporter_handles_empty_results(tmp_path):
    output_path = tmp_path / "report.md"
    MarkdownReporter().render([], str(output_path))
    content = output_path.read_text(encoding='utf-8')
    assert content.startswith("# evalkit report")
    assert "0 examples" in content


def test_markdown_reporter_latency_no_false_pass_fail_and_correct_units(tmp_path):
    results = [
        {"input": "q", "output": "a", "reference": None, "context": None, "scores": {"latency_ms": 123.456}}
    ]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')

    assert "123.5ms" in content
    assert "123.456 ✅" not in content
    assert "123.456 ❌" not in content
    # methodology caveat about raw measurements must mention it
    assert "raw measurements" in content
    assert "latency_ms" in content


def test_markdown_reporter_max_only_threshold_shown_correctly(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"latency_ms": 500.0}}]
    run_info = {"thresholds": [{"metric": "latency_ms", "min": None, "max": 3000}]}
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')

    assert "≤ 3000" in content
    assert "✅ Pass" in content


def test_markdown_reporter_max_threshold_failure_shown_correctly(tmp_path):
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"latency_ms": 5000.0}}]
    run_info = {"thresholds": [{"metric": "latency_ms", "min": None, "max": 3000}]}
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path), run_info=run_info)
    content = output_path.read_text(encoding='utf-8')

    assert "❌ Fail" in content


def test_markdown_reporter_no_raw_metrics_present_omits_caveat(tmp_path):
    """When no raw-value metric is in this particular report, don't mention
    latency_ms in the methodology text at all — it'd be a non-sequitur."""
    results = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"quality": 0.8}}]
    output_path = tmp_path / "report.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding='utf-8')
    assert "raw measurements" not in content


def test_html_and_json_reporters_still_accept_no_run_info(tmp_path):
    """Old call sites (or hand-written custom reporters) that don't pass
    run_info at all must keep working — this is the un-broken path."""
    results = [{"input": "q", "output": "a", "scores": {"m": 0.5}}]
    HTMLReporter().render(results, str(tmp_path / "r.html"))
    JSONReporter().render(results, str(tmp_path / "r.json"))
    assert (tmp_path / "r.html").exists()
    assert (tmp_path / "r.json").exists()


def test_markdown_reporter_includes_distribution_for_multi_value_metrics(tmp_path):
    results = [
        {"input": "q1", "output": "a1", "reference": None, "context": None, "scores": {"quality": 0.2}},
        {"input": "q2", "output": "a2", "reference": None, "context": None, "scores": {"quality": 0.8}},
    ]
    output_path = tmp_path / "r.md"
    MarkdownReporter().render(results, str(output_path))
    content = output_path.read_text(encoding="utf-8")
    assert "## Distribution" in content
    assert "| Metric | Mean | Median | Min | P5 | P95 | Max |" in content
    assert "| quality |" in content
