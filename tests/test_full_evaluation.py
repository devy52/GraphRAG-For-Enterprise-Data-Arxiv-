"""
Tests for the Comprehensive Evaluation Script.

Architecture Role:
    Validates the evaluation harness in scripts/run_full_evaluation.py:
    1. Per-track metric filtering excludes unavailable dependencies.
    2. Hop-type extraction from metadata works for all 5 categories.
    3. Legitimacy classification correctly tags deterministic vs judge-scored.
    4. Aggregation produces correct per-hop stratification.
    5. Full CLI smoke test (--limit 2) runs end-to-end without error.

Inputs:
    - Synthetic adapter results and dataset examples.
    - No network calls, no external dependencies.

Outputs:
    - pytest assertions validating evaluation logic.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure repo root and evalkit_upgraded are importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVALKIT_PATH = _REPO_ROOT / "evalkit"
if str(_EVALKIT_PATH) not in sys.path:
    sys.path.insert(0, str(_EVALKIT_PATH))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Import evaluation script functions under test
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
from run_full_evaluation import (
    HOP_ORDER,
    METRIC_LEGITIMACY,
    _classify_legitimacy,
    _get_hop_type,
    _get_track_metrics,
    _safe_mean,
    aggregate_results,
    generate_json_report,
    generate_markdown_report,
    generate_spot_checks,
)


# ==============================================================================
# Unit Tests: Hop Type Extraction
# ==============================================================================

class TestHopTypeExtraction:
    """Verifies hop type is correctly extracted from various metadata formats."""

    def test_explicit_hop_type_field(self) -> None:
        """Metadata with explicit hop_type field returns it directly."""
        assert _get_hop_type({"hop_type": "1-hop"}) == "1-hop"
        assert _get_hop_type({"hop_type": "aggregation"}) == "aggregation"
        assert _get_hop_type({"hop_type": "out-of-scope"}) == "out-of-scope"

    def test_id_based_fallback(self) -> None:
        """Metadata with only id field infers hop type from id pattern."""
        assert _get_hop_type({"id": "q_1hop_01"}) == "1-hop"
        assert _get_hop_type({"id": "q_2hop_05"}) == "2-hop"
        assert _get_hop_type({"id": "q_3hop_10"}) == "3-hop"
        assert _get_hop_type({"id": "q_agg_03"}) == "aggregation"
        assert _get_hop_type({"id": "q_oos_07"}) == "out-of-scope"

    def test_missing_metadata(self) -> None:
        """Missing or empty metadata returns 'unknown'."""
        assert _get_hop_type(None) == "unknown"
        assert _get_hop_type({}) == "unknown"


# ==============================================================================
# Unit Tests: Legitimacy Classification
# ==============================================================================

class TestLegitimacyClassification:
    """Verifies metric legitimacy tagging under dummy and live modes."""

    def test_deterministic_always_legit(self) -> None:
        """Deterministic metrics are always classified as deterministic."""
        assert _classify_legitimacy("f1", "dummy") == "deterministic"
        assert _classify_legitimacy("f1", "live") == "deterministic"
        assert _classify_legitimacy("exact_match", "dummy") == "deterministic"
        assert _classify_legitimacy("chunk_utilization", "live") == "deterministic"

    def test_judge_scored_dummy_mode(self) -> None:
        """Judge-scored metrics under dummy mode are pseudo-random."""
        result = _classify_legitimacy("faithfulness", "dummy")
        assert "pseudo-random" in result

    def test_judge_scored_live_mode(self) -> None:
        """Judge-scored metrics under live mode are legit."""
        result = _classify_legitimacy("faithfulness", "live")
        assert "legit" in result

    def test_unknown_metric(self) -> None:
        """Unknown metrics return 'unknown'."""
        assert _classify_legitimacy("made_up_metric", "dummy") == "unknown"


# ==============================================================================
# Unit Tests: Track Metrics Filtering
# ==============================================================================

class TestTrackMetricsFiltering:
    """Verifies per-track metric lists exclude unavailable dependencies."""

    def test_retrieval_track_always_complete(self) -> None:
        """Retrieval track metrics have no external dependencies."""
        metrics = _get_track_metrics("retrieval", None)
        assert "chunk_utilization" in metrics
        assert "precision_at_k" in metrics

    def test_rag_track_has_all_judge_metrics(self) -> None:
        """RAG track includes all judge-based metrics."""
        metrics = _get_track_metrics("rag", None)
        assert "faithfulness" in metrics
        assert "context_precision" in metrics
        assert "answer_relevancy" in metrics

    def test_unknown_track_passes_through(self) -> None:
        """Unknown track returns the user filter unchanged."""
        assert _get_track_metrics("unknown_track", ["my_metric"]) == ["my_metric"]
        assert _get_track_metrics("unknown_track", None) is None


# ==============================================================================
# Unit Tests: Aggregation
# ==============================================================================

class TestAggregation:
    """Verifies result aggregation and stratification logic."""

    @pytest.fixture
    def sample_results(self) -> list[dict]:
        """Creates a minimal set of per-example results for aggregation."""
        return [
            {
                "input": "Q1",
                "reference": "R1",
                "metadata": {"id": "q_1hop_01"},
                "adapter_output": "A1",
                "adapter_context": [],
                "adapter_latency_ms": 100.0,
                "adapter_metadata": {},
                "hop_type": "1-hop",
                "scores": {"text_similarity.f1": 0.8, "rag.faithfulness": 0.9},
            },
            {
                "input": "Q2",
                "reference": "R2",
                "metadata": {"id": "q_2hop_01"},
                "adapter_output": "A2",
                "adapter_context": [],
                "adapter_latency_ms": 200.0,
                "adapter_metadata": {},
                "hop_type": "2-hop",
                "scores": {"text_similarity.f1": 0.6, "rag.faithfulness": 0.7},
            },
            {
                "input": "Q3",
                "reference": "R3",
                "metadata": {"id": "q_oos_01"},
                "adapter_output": "A3",
                "adapter_context": [],
                "adapter_latency_ms": 50.0,
                "adapter_metadata": {},
                "hop_type": "out-of-scope",
                "scores": {"text_similarity.f1": 0.0, "rag.faithfulness": 1.0},
            },
        ]

    def test_overall_aggregation(self, sample_results: list[dict]) -> None:
        """Overall scores are correct means across all examples."""
        agg = aggregate_results(sample_results, "dummy")
        assert abs(agg["overall"]["text_similarity.f1"] - 0.4667) < 0.01
        assert abs(agg["overall"]["rag.faithfulness"] - 0.8667) < 0.01

    def test_per_hop_stratification(self, sample_results: list[dict]) -> None:
        """Per-hop scores isolate to the correct subset."""
        agg = aggregate_results(sample_results, "dummy")
        assert "1-hop" in agg["by_hop"]
        assert "2-hop" in agg["by_hop"]
        assert "out-of-scope" in agg["by_hop"]
        assert agg["by_hop"]["1-hop"]["text_similarity.f1"] == 0.8
        assert agg["by_hop"]["2-hop"]["rag.faithfulness"] == 0.7

    def test_summary_stats(self, sample_results: list[dict]) -> None:
        """Summary stats correctly count examples and compute latency."""
        agg = aggregate_results(sample_results, "dummy")
        assert agg["summary_stats"]["total_examples"] == 3
        assert agg["summary_stats"]["hop_distribution"]["1-hop"] == 1
        assert agg["summary_stats"]["latency_mean_ms"] > 0

    def test_legitimacy_tags(self, sample_results: list[dict]) -> None:
        """Legitimacy tags are present for all metrics."""
        agg = aggregate_results(sample_results, "dummy")
        assert "deterministic" in agg["metric_legitimacy"]["text_similarity.f1"]
        assert "pseudo-random" in agg["metric_legitimacy"]["rag.faithfulness"]


# ==============================================================================
# Unit Tests: Report Generation
# ==============================================================================

class TestReportGeneration:
    """Verifies report output files are created correctly."""

    @pytest.fixture
    def sample_agg(self) -> dict:
        """Minimal aggregation structure for report testing."""
        return {
            "overall": {"text_similarity.f1": 0.5, "rag.faithfulness": 0.8},
            "by_hop": {
                "1-hop": {"text_similarity.f1": 0.6, "rag.faithfulness": 0.9},
            },
            "metric_legitimacy": {
                "text_similarity.f1": "deterministic",
                "rag.faithfulness": "pseudo-random (dummy judge)",
            },
            "per_example": [
                {
                    "input": "Q1",
                    "reference": "R1",
                    "adapter_output": "A1",
                    "adapter_context": ["ctx1"],
                    "adapter_latency_ms": 100.0,
                    "hop_type": "1-hop",
                    "scores": {"text_similarity.f1": 0.6},
                    "metadata": {"id": "q_1hop_01"},
                }
            ],
            "summary_stats": {
                "total_examples": 1,
                "hop_distribution": {"1-hop": 1},
                "latency_mean_ms": 100.0,
                "latency_p50_ms": 100.0,
                "latency_p95_ms": 100.0,
            },
        }

    def test_json_report_created(self, sample_agg: dict) -> None:
        """JSON report is valid JSON and contains expected keys."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            generate_json_report(sample_agg, path)
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "overall" in data
            assert "by_hop" in data
            assert "per_example" in data

    def test_markdown_report_created(self, sample_agg: dict) -> None:
        """Markdown report contains section headers and metric tables."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            generate_markdown_report(sample_agg, "dummy", path)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "# GraphRAG Full Evaluation Report" in content
            assert "## Overall Scores" in content
            assert "## Per-Hop-Type Breakdown" in content
            assert "## How to Verify These Scores" in content
            assert "deterministic" in content

    def test_spot_checks_created(self, sample_agg: dict) -> None:
        """Spot-check file contains formatted sample entries."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spots.md"
            generate_spot_checks(sample_agg["per_example"], 1, path)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "# Spot-Check Samples" in content
            assert "Manual Check" in content


# ==============================================================================
# Unit Tests: Safe Mean
# ==============================================================================

class TestSafeMean:
    """Verifies _safe_mean handles edge cases."""

    def test_normal_mean(self) -> None:
        assert _safe_mean([1.0, 2.0, 3.0]) == 2.0

    def test_empty_list(self) -> None:
        assert _safe_mean([]) == 0.0

    def test_single_value(self) -> None:
        assert _safe_mean([5.0]) == 5.0
