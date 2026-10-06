"""
Unit Tests for Parameterized Graph Query Engine and Cypher Templates.

Architecture Role:
    Validates Phase 4 (Parameterized Graph Query Engine). Verifies that the Cypher template catalog
    is complete and syntactically valid, that query intent correctly routes to pre-compiled templates,
    and that graph record rows are properly converted into factual statements with source chunk citations.

Invariants Tested:
    1. Template catalog integrity (all enum types have defined templates and required parameter bindings).
    2. Intent and keyword routing to appropriate 1-hop, 2-hop, and 3-hop templates.
    3. Entity recognition against registered canonical entities and aliases.
    4. Statement formatting and deduplication of `source_chunk_id` citations.
"""

import pytest

from src.graph.models import EntityType, ResolvedEntity
from src.graph.query_engine import GraphQueryEngine, GraphQueryResult
from src.graph.resolver import EntityResolver
from src.graph.templates import CYPHER_TEMPLATES, CypherTemplate, QueryTemplateType


def test_cypher_template_catalog_integrity() -> None:
    """
    Test Objective:
        Verify that all `QueryTemplateType` enum values have complete, valid template definitions
        in `CYPHER_TEMPLATES`.

    Assertions:
        - Every QueryTemplateType is registered.
        - Cypher query is non-empty and contains parameter bindings matching required_parameters.
        - Hop count is a positive integer between 1 and 3.
    """
    # Step 1: Iterate over all enum values in QueryTemplateType
    for template_type in QueryTemplateType:
        assert template_type in CYPHER_TEMPLATES
        template = CYPHER_TEMPLATES[template_type]

        # Step 2: Validate template structure and non-empty query
        assert isinstance(template, CypherTemplate)
        assert len(template.cypher_query.strip()) > 0
        assert len(template.required_parameters) >= 1
        assert 1 <= template.hop_count <= 3

        # Step 3: Check parameter placeholder presence in Cypher string
        for param in template.required_parameters:
            assert f"${param}" in template.cypher_query


def test_query_engine_template_selection() -> None:
    """
    Test Objective:
        Verify that `GraphQueryEngine.select_template` accurately classifies user intent keywords
        into the appropriate parameterized Cypher template.

    Assertions:
        - Citation queries route to CITATION_CHAIN.
        - Extension queries route to METHOD_ANCESTRY_EXTENDS.
        - Comparison queries route to METHOD_BENCHMARK_COMPARISONS.
        - Co-authorship queries route to CO_AUTHORSHIP_NETWORK.
        - Authorship queries route to PAPERS_BY_AUTHOR.
    """
    # Step 1: Initialize query engine
    engine = GraphQueryEngine()

    # Step 2: Test Citation Chain selection
    t1, p1 = engine.select_template("Which papers cite the RAG paper?", [("RAG Paper", EntityType.PAPER)])
    assert t1 == QueryTemplateType.CITATION_CHAIN
    assert p1 == {"paper_title": "RAG Paper"}

    # Step 3: Test Method Ancestry selection
    t2, p2 = engine.select_template("What methods extend or build upon DPR?", [("DPR", EntityType.METHOD)])
    assert t2 == QueryTemplateType.METHOD_ANCESTRY_EXTENDS
    assert p2 == {"method_name": "DPR"}

    # Step 4: Test Benchmark Comparison selection
    t3, p3 = engine.select_template("Compare methods versus BM25 on the benchmark", [("BM25", EntityType.METHOD)])
    assert t3 == QueryTemplateType.METHOD_BENCHMARK_COMPARISONS
    assert p3 == {"method_name": "BM25"}

    # Step 5: Test Co-authorship selection
    t4, p4 = engine.select_template("Who collaborated or co-authored with Patrick Lewis?", [("Patrick Lewis", EntityType.AUTHOR)])
    assert t4 == QueryTemplateType.CO_AUTHORSHIP_NETWORK
    assert p4 == {"author_name": "Patrick Lewis"}

    # Step 6: Test Authorship selection
    t5, p5 = engine.select_template("Who wrote this paper?", [("Patrick Lewis", EntityType.AUTHOR)])
    assert t5 == QueryTemplateType.PAPERS_BY_AUTHOR
    assert p5 == {"author_name": "Patrick Lewis"}


def test_entity_identification_in_text() -> None:
    """
    Test Objective:
        Verify that `GraphQueryEngine.identify_entities_in_text` locates registered canonical entities
        and their aliases within free-form question text.

    Assertions:
        - Registered canonical name is matched.
        - Registered alias is matched to its canonical parent.
    """
    # Step 1: Prepare EntityResolver with known canonical entities and aliases
    resolver = EntityResolver()
    resolver.registry[(EntityType.METHOD, "Dense Passage Retrieval")] = ResolvedEntity(
        canonical_name="Dense Passage Retrieval",
        entity_type=EntityType.METHOD,
        aliases=["DPR", "dense retriever"],
    )
    resolver.registry[(EntityType.AUTHOR, "Patrick Lewis")] = ResolvedEntity(
        canonical_name="Patrick Lewis",
        entity_type=EntityType.AUTHOR,
        aliases=["P. Lewis"],
    )

    # Step 2: Initialize query engine with configured resolver
    engine = GraphQueryEngine(resolver=resolver)

    # Step 3: Test text with alias mention "DPR"
    matches1 = engine.identify_entities_in_text("What models build upon DPR?")
    assert len(matches1) == 1
    assert matches1[0] == ("Dense Passage Retrieval", EntityType.METHOD)

    # Step 4: Test text with author alias "P. Lewis"
    matches2 = engine.identify_entities_in_text("List papers authored by P. Lewis")
    assert len(matches2) == 1
    assert matches2[0] == ("Patrick Lewis", EntityType.AUTHOR)


def test_format_records_to_statements() -> None:
    """
    Test Objective:
        Verify that raw Neo4j record dictionaries format into human-readable sentences
        with grounded [chunk: ...] annotations.

    Assertions:
        - Output statements contain readable domain relationships.
        - `chunk_ids` are extracted and deduplicated.
    """
    # Step 1: Initialize query engine
    engine = GraphQueryEngine()

    # Step 2: Test 1-hop PAPERS_BY_AUTHOR formatting
    records1 = [
        {"author_name": "Patrick Lewis", "paper_title": "RAG Paper", "source_chunk_id": "chunk_001"},
        {"author_name": "Patrick Lewis", "paper_title": "DPR Paper", "source_chunk_id": "chunk_002"},
    ]
    statements1, chunk_ids1 = engine.format_records_to_statements(
        QueryTemplateType.PAPERS_BY_AUTHOR,
        records1,
    )
    assert len(statements1) == 2
    assert statements1[0] == "Patrick Lewis authored paper 'RAG Paper' [chunk: chunk_001]."
    assert chunk_ids1 == ["chunk_001", "chunk_002"]

    # Step 3: Test 2-hop METHOD_ANCESTRY_EXTENDS formatting
    records2 = [
        {"method_chain": ["RAG-Token", "RAG-Sequence", "DPR"], "chunk_ids": ["chunk_010", "chunk_011"]},
    ]
    statements2, chunk_ids2 = engine.format_records_to_statements(
        QueryTemplateType.METHOD_ANCESTRY_EXTENDS,
        records2,
    )
    assert len(statements2) == 1
    assert statements2[0] == "Method Lineage: RAG-Token -> extends -> RAG-Sequence -> extends -> DPR [chunk: chunk_010] [chunk: chunk_011]."
    assert chunk_ids2 == ["chunk_010", "chunk_011"]


@pytest.mark.asyncio
async def test_ego_neighborhood_formatting_and_fallback() -> None:
    """
    Test Objective:
        Verify that EGO_NEIGHBORHOOD formats 1-hop connected subgraph statements and that
        GraphQueryEngine falls back to EGO_NEIGHBORHOOD when primary template returns 0 records.
    """
    from unittest.mock import AsyncMock, MagicMock

    engine = GraphQueryEngine()

    # Step 1: Test formatting
    records = [
        {
            "entity": "Patrick Lewis",
            "relationship": "AUTHORED_BY",
            "neighbor_name": "Retrieval-Augmented Generation",
            "neighbor_type": "Paper",
            "source_chunk_id": "chunk_ego_01",
        }
    ]
    statements, cids = engine.format_records_to_statements(
        QueryTemplateType.EGO_NEIGHBORHOOD,
        records,
    )
    assert len(statements) == 1
    assert statements[0] == "Entity 'Patrick Lewis' -[:AUTHORED_BY]- 'Retrieval-Augmented Generation' (Paper) [chunk: chunk_ego_01]."
    assert cids == ["chunk_ego_01"]

    # Step 2: Register entity in resolver
    engine.resolver.registry[(EntityType.AUTHOR, "Patrick Lewis")] = ResolvedEntity(
        canonical_name="Patrick Lewis",
        entity_type=EntityType.AUTHOR,
        aliases=["P. Lewis"],
    )

    # Step 3: Mock execute_query: primary returns 0 records, ego returns 1 record
    call_counts = {"primary": 0, "ego": 0}

    async def mock_execute(template_type, params):
        if template_type == QueryTemplateType.EGO_NEIGHBORHOOD:
            call_counts["ego"] += 1
            return GraphQueryResult(
                template_type=template_type,
                parameters=params,
                raw_records=records,
                formatted_statements=statements,
                source_chunk_ids=cids,
                latency_ms=5.0,
            )
        call_counts["primary"] += 1
        return GraphQueryResult(
            template_type=template_type,
            parameters=params,
            raw_records=[],
            formatted_statements=[],
            source_chunk_ids=[],
            latency_ms=5.0,
        )

    engine.execute_query = AsyncMock(side_effect=mock_execute)

    # Step 4: Execute query that mentions Patrick Lewis
    res = await engine.query("What publications did Patrick Lewis author?")
    assert call_counts["primary"] == 1
    assert call_counts["ego"] == 1
    assert res.template_type == QueryTemplateType.EGO_NEIGHBORHOOD
    assert len(res.formatted_statements) == 1

