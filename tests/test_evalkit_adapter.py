"""
Unit Tests for Evalkit GraphRAG Adapter & Dataset Exporter.

Architecture Role:
    Validates testing integration with the external `evalkit` evaluation framework:
    1. Canonical dataset export to evalkit JSONL format.
    2. AdapterResponse generation with ground truth context, latency, and provenance metadata.
    3. Resilient fallback between HTTP client and in-process execution.
"""

import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from eval_adapter import GraphRAGAdapter
from evalkit.contracts.adapter import AdapterResponse
from scripts.export_evalkit_dataset import export_dataset


def test_evalkit_dataset_export() -> None:
    """
    Verifies that the canonical dataset exports into valid evalkit EvalExample JSONL.
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        count = export_dataset(tmp_path)
        assert count == 50, f"Expected 50 questions exported, got {count}"

        # Verify each line conforms to evalkit specification
        with open(tmp_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                assert "input" in data
                assert "reference" in data
                assert "metadata" in data
                assert "id" in data["metadata"]
                assert "hop_type" in data["metadata"]
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_evalkit_adapter_mocked_run() -> None:
    """
    Verifies that GraphRAGAdapter formats AdapterResponse correctly with
    output text, formatted context, latency, and query provenance metadata.
    """
    adapter = GraphRAGAdapter()

    fake_response = {
        "answer": "Patrick Lewis authored Retrieval-Augmented Generation [chunk_01].",
        "route_taken": "graph",
        "citations": ["chunk_01"],
        "is_grounded": True,
        "from_cache": False,
        "graph_facts": ["'Patrick Lewis' authored 'Retrieval-Augmented Generation' [chunk: chunk_01]"],
        "retrieved_chunks": ["Raw text passage from chunk 01."],
        "latency_breakdown_ms": {"total_request_ms": 142.5},
    }

    mock_runner = MagicMock()
    mock_runner.query.return_value = fake_response

    with patch.object(adapter, "_get_async_runner", return_value=mock_runner):
        with patch("httpx.Client.post", side_effect=Exception("Server offline")):
            response = adapter.run("Who authored RAG?", metadata={"id": "q_test_01"})

    assert isinstance(response, AdapterResponse)
    assert response.output == fake_response["answer"]
    assert response.latency_ms == 142.5
    assert len(response.context) == 2
    assert "[graph]" in response.context[0]
    assert "[retrieved]" in response.context[1]
    assert response.metadata["route_taken"] == "graph"
    assert response.metadata["citations"] == ["chunk_01"]
    assert response.metadata["is_grounded"] is True
    assert response.metadata["original_question_id"] == "q_test_01"
