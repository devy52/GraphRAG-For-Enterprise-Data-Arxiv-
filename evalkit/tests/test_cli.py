from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest


@pytest.fixture()
def rag_project(tmp_path):
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "input": "When was it built?",
                "context": ["It was built in 1889."],
                "metadata": {"precomputed_output": "It was built in 1889."},
            }
        )
        + "\n"
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent(
            f"""
            track: rag
            dataset: {dataset}
            adapter: static
            metrics: [faithfulness]
            judge_backend: dummy
            judge_model: dummy
            reporter: json
            output: {tmp_path / "report.json"}
            """
        )
    )
    return tmp_path, config


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "evalkit.cli", *args],
        capture_output=True,
        text=True,
    )


def test_cli_run_writes_report(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config))
    assert result.returncode == 0, result.stderr
    assert "faithfulness" in result.stdout
    assert (tmp_path / "report.json").exists()


def test_cli_assert_passes_when_threshold_met(rag_project):
    tmp_path, config = rag_project
    config.write_text(config.read_text() + "thresholds:\n  - metric: faithfulness\n    min: 0.0\n")
    result = _run_cli("assert", "--config", str(config))
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stdout.lower()


def test_cli_assert_fails_when_threshold_not_met(rag_project):
    tmp_path, config = rag_project
    config.write_text(config.read_text() + "thresholds:\n  - metric: faithfulness\n    min: 1.1\n")
    result = _run_cli("assert", "--config", str(config))
    assert result.returncode == 1
    assert "failed" in result.stdout.lower()


def test_cli_run_with_missing_config_fails_cleanly(tmp_path):
    result = _run_cli("run", "--config", str(tmp_path / "nonexistent.yaml"))
    assert result.returncode == 2
    assert "Config error:" in result.stderr


def test_cli_run_with_missing_dataset_fails_with_execution_error(rag_project):
    tmp_path, config = rag_project
    config.write_text(config.read_text().replace("data.jsonl", "missing.jsonl"))
    result = _run_cli("run", "--config", str(config))
    assert result.returncode == 3
    assert "Execution error:" in result.stderr


def test_cli_compare(rag_project):
    tmp_path, config_a = rag_project
    config_b = tmp_path / "config_b.yaml"
    config_b.write_text(config_a.read_text().replace("report.json", "report_b.json"))
    result = _run_cli("compare", "--config-a", str(config_a), "--config-b", str(config_b))
    assert result.returncode == 0, result.stderr
    assert "faithfulness" in result.stdout
    assert "diff" in result.stdout


def test_cli_run_shows_cache_stats_by_default(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config))
    assert result.returncode == 0, result.stderr
    assert "Cache:" in result.stdout
    assert (tmp_path / ".evalkit" / "cache").exists()


def test_cli_run_no_cache_flag_skips_cache_entirely(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config), "--no-cache")
    assert result.returncode == 0, result.stderr
    assert "Cache:" not in result.stdout
    assert not (tmp_path / ".evalkit" / "cache").exists()


def test_cli_run_second_invocation_hits_cache(rag_project):
    """Two separate CLI process invocations, same config -> the second
    must report a cache hit, proving the cache persists across process
    boundaries, not just within one Python process."""
    tmp_path, config = rag_project
    _run_cli("run", "--config", str(config))
    result = _run_cli("run", "--config", str(config))
    assert result.returncode == 0, result.stderr
    assert "1 hit" in result.stdout


def test_cli_concurrency_flag_accepted(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config), "--concurrency", "4")
    assert result.returncode == 0, result.stderr
    assert "faithfulness" in result.stdout


def test_cli_cache_clear(rag_project):
    tmp_path, config = rag_project
    _run_cli("run", "--config", str(config))  # populate cache
    cache_dir = tmp_path / ".evalkit" / "cache"
    assert list(cache_dir.glob("*.json"))

    result = _run_cli("cache", "clear", "--cache-dir", str(cache_dir))
    assert result.returncode == 0, result.stderr
    assert "Cleared" in result.stdout
    assert not list(cache_dir.glob("*.json"))


def test_cli_cache_clear_on_empty_dir(tmp_path):
    result = _run_cli("cache", "clear", "--cache-dir", str(tmp_path / "nonexistent"))
    assert result.returncode == 0, result.stderr
    assert "Cleared 0" in result.stdout


# -- Run store / diff --------------------------------------------------------


def test_cli_run_saves_a_run_by_default(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config))
    assert result.returncode == 0, result.stderr
    assert "Run saved as:" in result.stdout
    assert list((tmp_path / ".evalkit" / "runs").glob("*.json"))


def test_cli_run_no_save_run_flag_skips_saving(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config), "--no-save-run")
    assert result.returncode == 0, result.stderr
    assert "Run saved as:" not in result.stdout
    assert not (tmp_path / ".evalkit" / "runs").exists()


def test_cli_run_with_explicit_run_id(rag_project):
    tmp_path, config = rag_project
    result = _run_cli("run", "--config", str(config), "--run-id", "my-baseline")
    assert result.returncode == 0, result.stderr
    assert "my-baseline" in result.stdout
    assert (tmp_path / ".evalkit" / "runs" / "my-baseline.json").exists()


def test_cli_runs_list(rag_project):
    tmp_path, config = rag_project
    _run_cli("run", "--config", str(config), "--run-id", "run-one")
    _run_cli("run", "--config", str(config), "--run-id", "run-two")

    result = _run_cli("runs", "list", "--runs-dir", str(tmp_path / ".evalkit" / "runs"))
    assert result.returncode == 0, result.stderr
    assert "run-one" in result.stdout
    assert "run-two" in result.stdout


def test_cli_runs_list_empty(tmp_path):
    result = _run_cli("runs", "list", "--runs-dir", str(tmp_path / "nonexistent"))
    assert result.returncode == 0, result.stderr
    assert "No runs stored" in result.stdout


def test_cli_diff_two_saved_runs(rag_project):
    tmp_path, config = rag_project
    _run_cli("run", "--config", str(config), "--run-id", "baseline")
    _run_cli("run", "--config", str(config), "--run-id", "candidate")

    runs_dir = str(tmp_path / ".evalkit" / "runs")
    result = _run_cli("diff", "baseline", "candidate", "--runs-dir", runs_dir)
    assert result.returncode == 0, result.stderr
    assert "faithfulness" in result.stdout
    # identical config run twice -> identical scores -> no regressions
    assert "No per-example regressions found." in result.stdout


def test_cli_diff_missing_run_fails_with_clear_message(tmp_path):
    result = _run_cli("diff", "nonexistent-a", "nonexistent-b", "--runs-dir", str(tmp_path / ".evalkit" / "runs"))
    assert result.returncode != 0


def test_cli_compare_shows_no_regressions_for_identical_runs(rag_project):
    tmp_path, config_a = rag_project
    config_b = tmp_path / "config_b.yaml"
    config_b.write_text(config_a.read_text().replace("report.json", "report_b.json"))
    result = _run_cli("compare", "--config-a", str(config_a), "--config-b", str(config_b))
    assert result.returncode == 0, result.stderr
    assert "No per-example regressions found." in result.stdout
