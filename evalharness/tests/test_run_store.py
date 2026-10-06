from __future__ import annotations

import pytest

from evalharness.core.config import EvalConfig
from evalharness.core.run_store import RunStore, generate_run_id
from evalharness.core.runner import EvalResult


def _make_result(track="generic"):
    config = EvalConfig(track=track, dataset="d.jsonl", adapter="static")
    per_example = [{"input": "q", "output": "a", "reference": None, "context": None, "scores": {"quality": 0.8}}]
    return EvalResult(config, per_example, cache_stats={"hits": 1, "misses": 2})


def test_generate_run_id_is_unique():
    ids = {generate_run_id() for _ in range(20)}
    assert len(ids) == 20


def test_save_and_load_roundtrip(tmp_path):
    store = RunStore(str(tmp_path / "runs"))
    result = _make_result()

    run_id = store.save(result, run_id="my-baseline")
    assert run_id == "my-baseline"

    loaded = store.load("my-baseline")
    assert loaded["run_id"] == "my-baseline"
    assert loaded["track"] == "generic"
    assert loaded["dataset"] == "d.jsonl"
    assert loaded["aggregate"] == {"quality": 0.8}
    assert loaded["cache_stats"] == {"hits": 1, "misses": 2}
    assert loaded["per_example"] == result.per_example
    assert "created_at" in loaded


def test_save_without_run_id_autogenerates_one(tmp_path):
    store = RunStore(str(tmp_path / "runs"))
    run_id = store.save(_make_result())
    assert run_id  # non-empty
    assert store.load(run_id)["run_id"] == run_id


def test_load_missing_run_raises_with_helpful_message(tmp_path):
    store = RunStore(str(tmp_path / "runs"))
    store.save(_make_result(), run_id="exists")

    with pytest.raises(FileNotFoundError, match="exists"):
        store.load("does-not-exist")


def test_load_missing_run_with_no_runs_at_all(tmp_path):
    store = RunStore(str(tmp_path / "empty_runs"))
    with pytest.raises(FileNotFoundError, match="No runs stored yet"):
        store.load("anything")


def test_list_runs_empty_when_dir_missing(tmp_path):
    store = RunStore(str(tmp_path / "never_created"))
    assert store.list_runs() == []


def test_list_runs_sorted(tmp_path):
    store = RunStore(str(tmp_path / "runs"))
    store.save(_make_result(), run_id="run-b")
    store.save(_make_result(), run_id="run-a")
    store.save(_make_result(), run_id="run-c")
    assert store.list_runs() == ["run-a", "run-b", "run-c"]


def test_run_artifact_is_plain_readable_json(tmp_path):
    """Auditability requirement, same as the cache: a stored run must be a
    plain file, openable and readable, not opaque."""
    import json

    runs_dir = tmp_path / "runs"
    store = RunStore(str(runs_dir))
    store.save(_make_result(), run_id="check-me")

    files = list(runs_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["run_id"] == "check-me"
