"""
Unit and Integration Tests for Answer Synthesizer, Citation Validator, and Response Cache.

Architecture Role:
    Validates Phase 6 components:
    1. Deterministic citation extraction and provenance verification.
    2. Strict rejection of hallucinated chunk IDs.
    3. Context assembly explicitly labeling `[graph]` and `[retrieved]` sources.
    4. Multi-turn retry and regeneration loop upon citation failure.
    5. Query response caching with canonical normalization.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from src.core.cache import QueryResponseCache
from src.router.models import RetrievalContext, RouteDecision
from src.synthesis.synthesizer import AnswerSynthesizer, SynthesizedAnswer
from src.synthesis.validator import CitationValidationResult, CitationValidator
from src.vector.models import VectorSearchResult


# ==============================================================================
# Fixtures & Test Data
# ==============================================================================
@pytest.fixture
def sample_retrieval_context() -> RetrievalContext:
    """Provides a realistic multi-modal RetrievalContext for testing."""
    chunks = [
        VectorSearchResult(
            chunk_id="chunk_dpr_intro_01",
            document_id="doc_dpr_2020",
            paper_title="Dense Passage Retrieval for Open-Domain Question Answering",
            section_path="1. Introduction",
            text="Open-domain question answering relies on efficient passage retrieval.",
            entity_ids=["Dense Passage Retrieval", "Open-Domain QA"],
            score=0.94,
        ),
        VectorSearchResult(
            chunk_id="chunk_dpr_eval_02",
            document_id="doc_dpr_2020",
            paper_title="Dense Passage Retrieval for Open-Domain Question Answering",
            section_path="4. Experiments",
            text="DPR achieves a top-20 passage retrieval accuracy of 78.4% on Natural Questions.",
            entity_ids=["Dense Passage Retrieval", "Natural Questions"],
            score=0.89,
        ),
    ]
    facts = [
        "'Dense Passage Retrieval' extends 'BM25' [chunk: chunk_ancestor_01]",
        "'Patrick Lewis' authored 'Dense Passage Retrieval' [chunk: chunk_author_01]",
    ]
    return RetrievalContext(
        query="What methods extend BM25 and how accurate is DPR?",
        route=RouteDecision.BOTH,
        graph_facts=facts,
        retrieved_chunks=chunks,
        cited_chunk_ids=["chunk_ancestor_01", "chunk_author_01", "chunk_dpr_intro_01", "chunk_dpr_eval_02"],
        latency_ms={"routing_ms": 1.2, "graph_ms": 10.4, "vector_ms": 8.1},
    )


# ==============================================================================
# Unit Tests: Citation Validator
# ==============================================================================
def test_citation_validator_extraction() -> None:
    """
    Verifies that the validator correctly extracts multiple citation bracket variations.
    """
    validator = CitationValidator()
    text = (
        "DPR extends BM25 [chunk_ancestor_01]. "
        "It achieves high top-20 accuracy [chunk: chunk_dpr_eval_02] "
        "and is documented in section 1 [doc_01.chunk_03]."
    )

    extracted = validator.extract_citations(text)
    assert "chunk_ancestor_01" in extracted
    assert "chunk_dpr_eval_02" in extracted
    assert "doc_01.chunk_03" in extracted
    assert len(extracted) == 3


def test_citation_validator_valid_citations() -> None:
    """
    Verifies that validation passes when all citations match allowed chunk IDs.
    """
    validator = CitationValidator()
    text = "DPR extends BM25 [chunk_01] and reaches 78.4% accuracy [chunk: chunk_02]."
    allowed = ["chunk_01", "chunk_02", "chunk_03"]

    result = validator.validate(text, allowed_chunk_ids=allowed)
    assert result.is_valid is True
    assert result.total_citations_found == 2
    assert result.valid_citations == ["chunk_01", "chunk_02"]
    assert len(result.hallucinated_citations) == 0
    assert result.error_message is None


def test_citation_validator_rejects_hallucinations() -> None:
    """
    Verifies that any citation not present in allowed chunk IDs is immediately flagged and rejected.
    """
    validator = CitationValidator()
    # 'chunk_fake_99' is hallucinated
    text = "DPR outperforms BM25 [chunk_01] according to recent benchmarks [chunk_fake_99]."
    allowed = ["chunk_01", "chunk_02"]

    result = validator.validate(text, allowed_chunk_ids=allowed)
    assert result.is_valid is False
    assert result.total_citations_found == 2
    assert "chunk_01" in result.valid_citations
    assert "chunk_fake_99" in result.hallucinated_citations
    assert result.error_message is not None
    assert "hallucinated citation(s)" in result.error_message


def test_citation_validator_zero_citations_substantive() -> None:
    """
    Verifies that a substantive answer without citations fails validation if required.
    """
    validator = CitationValidator()
    text = "DPR is a retrieval method that works very well."
    allowed = ["chunk_01", "chunk_02"]

    result = validator.validate(text, allowed_chunk_ids=allowed, require_at_least_one=True)
    assert result.is_valid is False
    assert result.total_citations_found == 0
    assert "zero citations" in result.error_message.lower()


# ==============================================================================
# Unit Tests: Query Response Cache
# ==============================================================================
def test_query_response_cache_normalization_and_lru() -> None:
    """
    Verifies canonical query normalization and LRU capacity eviction.
    """
    cache = QueryResponseCache(max_entries=2)

    # Step 1: Verify whitespace and casing normalization produce identical keys
    key1 = cache.compute_key("What is Dense Passage Retrieval?")
    key2 = cache.compute_key("  what   is  dense passage retrieval  ")
    assert key1 == key2

    # Step 2: Set and retrieve
    cache.set("Query One", "Answer 1")
    cache.set("Query Two", "Answer 2")

    assert cache.get("query one") == "Answer 1"
    assert cache.get("query two") == "Answer 2"
    assert cache.get("unknown query") is None

    # Step 3: Eviction on capacity overflow
    # Accessing Query One makes Query Two the oldest
    cache.get("Query One")
    cache.set("Query Three", "Answer 3")

    # Query Two should be evicted
    assert cache.size() == 2
    assert cache.get("Query Two") is None
    assert cache.get("Query One") == "Answer 1"
    assert cache.get("Query Three") == "Answer 3"


# ==============================================================================
# Integration Tests: Answer Synthesizer
# ==============================================================================
@pytest.mark.asyncio
async def test_answer_synthesizer_context_assembly(
    sample_retrieval_context: RetrievalContext,
) -> None:
    """
    Verifies that context assembly explicitly partitions [graph] and [retrieved] sections.
    """
    synthesizer = AnswerSynthesizer()
    context_str, allowed_ids = synthesizer.assemble_context(sample_retrieval_context)

    # Check structural boundaries and explicit source tagging
    assert "=== KNOWLEDGE GRAPH FACTS ===" in context_str
    assert "[graph] Fact 1:" in context_str
    assert "=== RETRIEVED DOCUMENT PASSAGES ===" in context_str
    assert "[retrieved] [chunk_dpr_intro_01]" in context_str

    # Check allowed IDs aggregation
    assert "chunk_ancestor_01" in allowed_ids
    assert "chunk_dpr_intro_01" in allowed_ids
    assert "chunk_dpr_eval_02" in allowed_ids


@pytest.mark.asyncio
async def test_answer_synthesizer_offline_deterministic(
    sample_retrieval_context: RetrievalContext,
) -> None:
    """
    Verifies that offline synthesis generates a validated, grounded answer with verifiable citations.
    """
    synthesizer = AnswerSynthesizer()
    answer: SynthesizedAnswer = await synthesizer.synthesize(
        context=sample_retrieval_context,
        use_cache=False,
    )

    assert answer.validation_result.is_valid is True
    assert len(answer.cited_chunk_ids) > 0
    # Every cited chunk ID must be in the retrieval context's allowed IDs
    for cid in answer.cited_chunk_ids:
        assert cid in sample_retrieval_context.cited_chunk_ids

    assert "assembly_ms" in answer.latency_ms
    assert "synthesis_ms" in answer.latency_ms
    assert "validation_ms" in answer.latency_ms


@pytest.mark.asyncio
async def test_answer_synthesizer_caching(
    sample_retrieval_context: RetrievalContext,
) -> None:
    """
    Verifies that identical queries hit the cache on the second invocation.
    """
    synthesizer = AnswerSynthesizer()

    # First call -> uncached
    first_resp = await synthesizer.synthesize(sample_retrieval_context, use_cache=True)
    assert first_resp.from_cache is False

    # Second call -> cached
    second_resp = await synthesizer.synthesize(sample_retrieval_context, use_cache=True)
    assert second_resp.from_cache is True
    assert second_resp.answer == first_resp.answer


@pytest.mark.asyncio
async def test_answer_synthesizer_regeneration_on_hallucination(
    sample_retrieval_context: RetrievalContext,
) -> None:
    """
    Verifies that when an LLM hallucinates an invalid citation, the retry loop triggers regeneration.
    """
    synthesizer = AnswerSynthesizer()

    # Mock an LLM client where attempt 1 returns a hallucinated citation and attempt 2 returns a valid citation
    mock_llm = MagicMock()
    mock_resp_bad = MagicMock()
    mock_resp_bad.choices = [
        MagicMock(message=MagicMock(content="DPR extends BM25 [chunk_hallucinated_fake_99]."))
    ]
    mock_resp_good = MagicMock()
    mock_resp_good.choices = [
        MagicMock(message=MagicMock(content="DPR extends BM25 [chunk_ancestor_01]."))
    ]

    mock_llm.chat.completions.create = AsyncMock(
        side_effect=[mock_resp_bad, mock_resp_good]
    )
    synthesizer.llm_client = mock_llm

    result = await synthesizer.synthesize(sample_retrieval_context, max_retries=2, use_cache=False)

    # Must require 2 generation attempts
    assert result.generation_attempts == 2
    assert result.validation_result.is_valid is True
    assert "chunk_ancestor_01" in result.cited_chunk_ids
    assert mock_llm.chat.completions.create.call_count == 2
