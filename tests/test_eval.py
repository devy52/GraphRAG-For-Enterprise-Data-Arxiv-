"""
Unit and Integration Tests for Evaluation Dataset, Runner, and Reporter.

Architecture Role:
    Validates Phase 8 components:
    1. Stratified evaluation dataset structure and count integrity (50 questions across 5 categories).
    2. Benchmark runner execution across Plain Vector Baseline vs. Hybrid GraphRAG.
    3. Metrics computation (accuracy by hop, hallucination rate, p95 latency).
    4. Markdown comparison table generation and JSON report persistence.
"""

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.eval.dataset import (
    BenchmarkDataset,
    EvalHopType,
    EvalQuestion,
    get_canonical_evaluation_dataset,
)
from src.eval.report import BenchmarkReporter
from src.eval.runner import BenchmarkRunner, ComparativeBenchmarkResult
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import SynthesizedAnswer
from src.synthesis.validator import CitationValidationResult
from src.vector.models import VectorSearchResult


# ==============================================================================
# Unit Tests: Evaluation Dataset Integrity
# ==============================================================================
def test_canonical_dataset_stratification() -> None:
    """
    Verifies that the canonical benchmark dataset contains 50 questions
    evenly stratified with 10 questions per hop category.
    """
    dataset = get_canonical_evaluation_dataset()
    assert len(dataset.questions) == 50, f"Expected 50 questions, got {len(dataset.questions)}"

    # Check distribution across all 5 complexity categories
    for hop_type in EvalHopType:
        subset = dataset.filter_by_hop(hop_type)
        assert len(subset) == 10, f"Expected 10 questions for {hop_type.value}, got {len(subset)}"

    # Check question schema fields
    for q in dataset.questions:
        assert q.id.startswith("q_")
        assert len(q.question) > 10
        if q.hop_type == EvalHopType.OUT_OF_SCOPE:
            assert q.should_refuse is True
        else:
            assert len(q.expected_answer_keywords) > 0


# ==============================================================================
# Integration Tests: Benchmark Runner
# ==============================================================================
@pytest.mark.asyncio
async def test_benchmark_runner_execution() -> None:
    """
    Verifies that BenchmarkRunner executes over a representative question subset
    and computes metric records with calculated deltas.
    """
    # Create small 5-question test dataset (1 of each hop type)
    canonical = get_canonical_evaluation_dataset()
    test_questions = [
        canonical.filter_by_hop(EvalHopType.ONE_HOP)[0],
        canonical.filter_by_hop(EvalHopType.TWO_HOP)[0],
        canonical.filter_by_hop(EvalHopType.THREE_HOP)[0],
        canonical.filter_by_hop(EvalHopType.AGGREGATION)[0],
        canonical.filter_by_hop(EvalHopType.OUT_OF_SCOPE)[0],
    ]
    test_dataset = BenchmarkDataset(name="Test-Mini-Set", questions=test_questions)

    # Mock coordinator and synthesizer
    mock_coord = MagicMock()
    mock_retrieval_ctx = RetrievalContext(
        query="Test Question",
        route=RouteDecision.BOTH,
        graph_facts=["Patrick Lewis authored Dense Passage Retrieval [chunk: chunk_01]"],
        retrieved_chunks=[
            VectorSearchResult(
                chunk_id="chunk_01",
                document_id="doc_01",
                paper_title="DPR Paper",
                section_path="Abstract",
                text="Vladimir Karpukhin Barlas Oguz Patrick Lewis Sebastian Riedel Ethan Perez BM25 ANCE BART",
                score=0.92,
            )
        ],
        cited_chunk_ids=["chunk_01"],
    )
    mock_coord.retrieve = AsyncMock(return_value=mock_retrieval_ctx)

    mock_synth = MagicMock()
    mock_answer = SynthesizedAnswer(
        query="Test Question",
        answer="Vladimir Karpukhin and Patrick Lewis authored DPR [chunk_01]. No sufficient evidence for outside topics.",
        route=RouteDecision.BOTH,
        cited_chunk_ids=["chunk_01"],
        validation_result=CitationValidationResult(
            is_valid=True,
            total_citations_found=1,
            valid_citations=["chunk_01"],
            hallucinated_citations=[],
        ),
        generation_attempts=1,
        from_cache=False,
        latency_ms={"total_ms": 15.0},
    )
    mock_synth.synthesize = AsyncMock(return_value=mock_answer)

    mock_vector = MagicMock()
    mock_vector.similarity_search = AsyncMock(return_value=mock_retrieval_ctx.retrieved_chunks)

    runner = BenchmarkRunner(
        coordinator=mock_coord,
        synthesizer=mock_synth,
        vector_store=mock_vector,
    )

    result: ComparativeBenchmarkResult = await runner.run_benchmark(dataset=test_dataset)

    assert result.total_questions == 5
    assert result.hybrid_graphrag.citation_hallucination_rate == 0.0
    assert result.hybrid_graphrag.p95_latency_ms > 0
    assert result.vector_baseline.p95_latency_ms > 0
    assert "1-hop" in result.accuracy_delta_by_hop
    assert "2-hop" in result.accuracy_delta_by_hop
    assert "3-hop" in result.accuracy_delta_by_hop


# ==============================================================================
# Unit Tests: Benchmark Reporter
# ==============================================================================
def test_benchmark_reporter_markdown_and_json() -> None:
    """
    Verifies that the reporter produces valid markdown tables, saves JSON,
    and updates markdown documents safely.
    """
    from src.eval.runner import EvalMetricRecord

    mock_res = ComparativeBenchmarkResult(
        dataset_name="Test-Dataset",
        total_questions=50,
        vector_baseline=EvalMetricRecord(
            system_name="Plain Vector Baseline",
            accuracy_by_hop={"1-hop": 0.88, "2-hop": 0.52, "3-hop": 0.24, "aggregation": 0.60, "out-of-scope": 0.70},
            overall_accuracy=0.588,
            citation_hallucination_rate=0.185,
            p50_latency_ms=280.0,
            p95_latency_ms=380.0,
            mean_latency_ms=300.0,
        ),
        hybrid_graphrag=EvalMetricRecord(
            system_name="Hybrid GraphRAG",
            accuracy_by_hop={"1-hop": 0.915, "2-hop": 0.86, "3-hop": 0.79, "aggregation": 0.88, "out-of-scope": 1.0},
            overall_accuracy=0.889,
            citation_hallucination_rate=0.0,
            p50_latency_ms=450.0,
            p95_latency_ms=620.0,
            mean_latency_ms=490.0,
        ),
        accuracy_delta_by_hop={"1-hop": 3.5, "2-hop": 34.0, "3-hop": 55.0, "aggregation": 28.0, "out-of-scope": 30.0},
    )

    # 1. Generate Markdown Table
    table = BenchmarkReporter.generate_markdown_table(mock_res)
    assert "| Metric | Plain Vector Baseline | Hybrid GraphRAG | Improvement |" in table
    assert "**1-Hop Question Accuracy**" in table
    assert "**2-Hop Relational Accuracy**" in table
    assert "**3-Hop Multi-Hop Accuracy**" in table
    assert "**+55.0%**" in table
    assert "**0.0%** (Hard gate)" in table

    # 2. Save JSON Report to Temp File
    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = Path(tmp_dir) / "test_report.json"
        saved = BenchmarkReporter.save_json_report(mock_res, output_path=str(json_path))
        assert saved.exists()

        # 3. Test README updating
        mock_readme = Path(tmp_dir) / "README.md"
        mock_readme.write_text(
            "# Enterprise GraphRAG\n\n"
            "## Benchmark Results (vs. Plain Vector RAG)\n\n"
            "OLD TABLE CONTENT HERE\n\n"
            "---\n\n"
            "## Architecture\n",
            encoding="utf-8",
        )
        updated = BenchmarkReporter.update_readme_table(mock_res, readme_path=str(mock_readme))
        assert updated is True
        new_content = mock_readme.read_text(encoding="utf-8")
        assert "OLD TABLE CONTENT HERE" not in new_content
        assert "**3-Hop Multi-Hop Accuracy**" in new_content
        assert "## Architecture" in new_content
