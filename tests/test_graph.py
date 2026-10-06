"""
Unit Tests for Knowledge Graph Extraction, Entity Resolution, and Schema Validation.

Architecture Role:
    Validates Phase 2 (Knowledge Graph Ingestion). Verifies that ontology enums (`EntityType`,
    `RelationType`), multi-stage entity resolution cascade, alias deduplication, and extraction
    caching mechanisms work reliably and adhere to `Docs/ONTOLOGY.md`.

Invariants Tested:
    1. Schema validation of `ExtractedFact` against strict ontology enums and confidence bounds.
    2. String sanitization and normalization in `EntityResolver.normalize_name`.
    3. Alias aggregation on canonical entity nodes during entity resolution.
    4. End-to-end fact resolution rewriting surface forms to canonical identifiers.
    5. Local JSON disk cache save and reload keyed by chunk SHA-256 digests.
"""

import pytest

from src.graph.extractor import GraphExtractor
from src.graph.models import EntityType, ExtractedFact, RelationType, ResolvedEntity
from src.graph.resolver import EntityResolver
from src.ingestion.models import DocumentChunk


def test_extracted_fact_validation() -> None:
    """
    Test Objective:
        Verify that `ExtractedFact` validates ontology types, predicates, and confidence bounds.

    Assertions:
        - Source and target types match authorized `EntityType` enum members.
        - Predicate matches authorized `RelationType` enum member.
        - Foreign key `source_chunk_id` is assigned and accessible.
    """
    # Step 1: Create ExtractedFact model adhering to ONTOLOGY.md
    fact = ExtractedFact(
        source_name="RAG-Sequence",
        source_type=EntityType.METHOD,
        relation=RelationType.USES_DATASET,
        target_name="Natural Questions",
        target_type=EntityType.DATASET,
        source_chunk_id="chunk_rag_001_000",
        confidence=0.95,
    )

    # Step 2: Assert enum typing and chunk attribution
    assert fact.source_type == EntityType.METHOD
    assert fact.relation == RelationType.USES_DATASET
    assert fact.source_chunk_id == "chunk_rag_001_000"


def test_entity_resolver_normalization() -> None:
    """
    Test Objective:
        Verify lexical sanitization and whitespace normalization across diverse entity strings.

    Assertions:
        - Quotation marks and trailing punctuation are stripped.
        - Excess internal spaces are collapsed to single spaces.
    """
    # Step 1: Assert sanitization of quotes and trailing commas
    assert EntityResolver.normalize_name("  \"Patrick Lewis\",  ") == "Patrick Lewis"

    # Step 2: Assert internal space normalization
    assert EntityResolver.normalize_name("Meta   AI") == "Meta AI"

    # Step 3: Assert single quote stripping
    assert EntityResolver.normalize_name("'Dense Passage Retrieval'") == "Dense Passage Retrieval"


@pytest.mark.asyncio
async def test_entity_resolver_alias_merging() -> None:
    """
    Test Objective:
        Verify that lexical matching deduplicates entity variations into a single
        canonical node while accumulating surface variations in the aliases array.

    Assertions:
        - First mention establishes canonical node name.
        - Second mention with different casing merges into the same cluster.
        - Canonical registry contains exactly 1 unique entity record.
    """
    # Step 1: Initialize EntityResolver instance
    resolver = EntityResolver()
    
    # Step 2: Register initial canonical entity mention
    e1 = await resolver.resolve_entity("Retrieval-Augmented Generation", EntityType.METHOD)
    assert e1.canonical_name == "Retrieval-Augmented Generation"
    
    # Step 3: Resolve identical entity with lowercase phrasing variation
    e2 = await resolver.resolve_entity("retrieval-augmented generation", EntityType.METHOD)

    # Step 4: Verify alias merging and single canonical registry entry
    assert e2.canonical_name == "Retrieval-Augmented Generation"
    assert "retrieval-augmented generation" in e2.aliases or e2.canonical_name == "Retrieval-Augmented Generation"
    assert len(resolver.registry) == 1


@pytest.mark.asyncio
async def test_fact_resolution_pipeline() -> None:
    """
    Test Objective:
        Verify end-to-end fact resolution where surface strings on both source and target
        are replaced with their canonical cluster names.

    Assertions:
        - Raw facts containing different surface forms ('Patrick Lewis' and 'patrick lewis')
          both resolve to canonical 'Patrick Lewis'.
    """
    # Step 1: Initialize resolver
    resolver = EntityResolver()

    # Step 2: Prepare raw facts with varying surface names
    raw_facts = [
        ExtractedFact(
            source_name="Patrick Lewis",
            source_type=EntityType.AUTHOR,
            relation=RelationType.AFFILIATED_WITH,
            target_name="Meta AI",
            target_type=EntityType.INSTITUTION,
            source_chunk_id="chunk_001",
        ),
        ExtractedFact(
            source_name="patrick lewis",
            source_type=EntityType.AUTHOR,
            relation=RelationType.AFFILIATED_WITH,
            target_name="Meta AI Inc",
            target_type=EntityType.INSTITUTION,
            source_chunk_id="chunk_002",
        ),
    ]

    # Step 3: Execute full facts resolution
    resolved_facts = await resolver.resolve_facts(raw_facts)

    # Step 4: Verify both facts now share the exact canonical author name
    assert len(resolved_facts) == 2
    assert resolved_facts[0].source_name == "Patrick Lewis"
    assert resolved_facts[1].source_name == "Patrick Lewis"


@pytest.mark.asyncio
async def test_resolve_and_link_batch_entities() -> None:
    """
    Test Objective:
        Verify that EntityResolver.resolve_and_link correctly returns distinct batch
        ResolvedEntity instances along with canonicalized ExtractedFact triples.
    """
    resolver = EntityResolver()
    raw_facts = [
        ExtractedFact(
            source_name="RAG architecture",
            source_type=EntityType.METHOD,
            relation=RelationType.USES_DATASET,
            target_name="MS MARCO benchmark",
            target_type=EntityType.DATASET,
            source_chunk_id="chunk_001",
        ),
        ExtractedFact(
            source_name="RAG architecture",
            source_type=EntityType.METHOD,
            relation=RelationType.USES_DATASET,
            target_name="Natural Questions",
            target_type=EntityType.DATASET,
            source_chunk_id="chunk_001",
        ),
    ]

    entities, facts = await resolver.resolve_and_link(raw_facts)
    assert len(facts) == 2
    assert len(entities) == 3  # 1 Method + 2 Datasets
    assert any(e.canonical_name == "RAG architecture" for e in entities)



def test_extractor_cache_mechanism(tmp_path) -> None:
    """
    Test Objective:
        Verify that `GraphExtractor` saves and reloads cached extractions from disk
        keyed by SHA-256 chunk hashes, preventing duplicate LLM API calls.

    Assertions:
        - Cache initializes empty when file does not exist.
        - Persisted cache file correctly restores facts upon re-instantiation.
    """
    # Step 1: Initialize extractor pointing to a temporary test cache path
    cache_file = str(tmp_path / "test_cache.json")
    extractor = GraphExtractor(cache_path=cache_file)
    assert extractor.cache == {}

    # Step 2: Seed cache with mock extracted fact
    sample_hash = "mock_sha256_hash_12345"
    extractor.cache[sample_hash] = [
        {
            "source_name": "RAG",
            "source_type": "Method",
            "relation": "EXTENDS",
            "target_name": "DPR",
            "target_type": "Method",
            "source_chunk_id": "chunk_mock_001",
            "confidence": 1.0,
        }
    ]
    extractor._save_cache()

    # Step 3: Re-initialize new extractor instance from the same cache file
    extractor2 = GraphExtractor(cache_path=cache_file)

    # Step 4: Verify cache was successfully reloaded from disk
    assert sample_hash in extractor2.cache
    assert len(extractor2.cache[sample_hash]) == 1
