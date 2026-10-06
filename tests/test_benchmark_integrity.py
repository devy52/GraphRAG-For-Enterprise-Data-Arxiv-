from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_v2_runner_never_injects_gold_reference_into_fallback():
    text = (ROOT / "scripts" / "run_benchmark_v2.py").read_text(encoding="utf-8")
    # Gold reference/expected facts may appear in comments or schema validation,
    # but never as retrieved evidence text in the runner.
    assert 'text=q.reference_answer' not in text
    assert '" ".join(q.expected_answer_keywords)' not in text


def test_v2_runner_has_dataset_fingerprint():
    text = (ROOT / "scripts" / "run_benchmark_v2.py").read_text(encoding="utf-8")
    assert "validate_v2_dataset" in text
    assert '"dataset_sha256"' in text


def test_no_question_id_accuracy_override_in_legacy_runner():
    text = (ROOT / "src" / "eval" / "runner.py").read_text(encoding="utf-8")
    assert not re.search(r'is_accurate\s*=\s*False\s*#.*question', text, re.I)
    assert 'q.id in (' not in text


def test_benchmark_dataset_has_complete_gold_for_answerable_questions():
    import json
    dataset = [json.loads(line) for line in (ROOT / "data" / "benchmark_v2_dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(dataset) == 50
    answerable = [q for q in dataset if q["answerable"]]
    unanswerable = [q for q in dataset if not q["answerable"]]
    assert len(answerable) == 40
    assert len(unanswerable) == 10
    assert all(q["gold_chunk_ids"] or q.get("gold_evidence") for q in answerable)
    assert all(q["required_facts"] for q in answerable)
    assert all(not q["gold_chunk_ids"] for q in unanswerable)
