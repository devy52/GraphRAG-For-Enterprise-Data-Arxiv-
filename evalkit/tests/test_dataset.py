from __future__ import annotations

import json

import pytest

from evalkit.core.dataset import EvalExample, load_dataset


def test_load_dataset_happy_path(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"input": "hi"}) + "\n")
    examples = load_dataset(str(path))
    assert examples == [EvalExample(input="hi")]


def test_load_dataset_skips_blank_lines(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"input": "a"}\n\n{"input": "b"}\n\n')
    examples = load_dataset(str(path))
    assert len(examples) == 2


def test_load_dataset_raises_with_line_number_on_bad_json(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"input": "a"}\nnot json at all\n{"input": "b"}\n')
    with pytest.raises(ValueError, match=r"data\.jsonl:2"):
        load_dataset(str(path))


def test_load_dataset_raises_on_missing_required_field(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(json.dumps({"reference": "no input field here"}) + "\n")
    with pytest.raises(Exception):  # pydantic ValidationError
        load_dataset(str(path))


def test_load_dataset_raises_on_empty_file(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="no examples"):
        load_dataset(str(path))


def test_load_dataset_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_dataset("/nonexistent/path/data.jsonl")


def test_eval_example_defaults():
    ex = EvalExample(input="hi")
    assert ex.reference is None
    assert ex.context is None
    assert ex.metadata == {}
