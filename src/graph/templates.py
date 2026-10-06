"""
Cypher Query Templates & Parameterized Catalog.

Architecture Role:
    Part of Phase 4 (Parameterized Graph Query Engine). Defines a pre-compiled, security-hardened
    catalog of Cypher query templates strictly aligned with `Docs/ONTOLOGY.md`.
    Prevents unconstrained Text-to-Cypher LLM hallucination and Cypher injection by strictly binding
    extracted entities as parameters into predefined traversal paths.

Supported Traversals:
    1-Hop Queries:
        - PAPERS_BY_AUTHOR: Direct authorship links (`Author <- AUTHORED_BY - Paper`).
        - METHODS_USED_IN_PAPER: Techniques applied in a paper (`Paper - USES_METHOD -> Method`).
        - DATASETS_USED_IN_PAPER: Evaluation benchmarks (`Paper - USES_DATASET -> Dataset`).
        - PAPERS_IN_VENUE: Publications in a conference/archive (`Paper - PUBLISHED_IN -> Venue`).
        - PAPERS_BY_TOPIC: Subject classifications (`Paper - HAS_TOPIC -> Topic`).
    2-Hop Queries:
        - METHOD_ANCESTRY_EXTENDS: Direct and 2-hop method lineages (`Method - EXTENDS*1..2 -> Method`).
        - METHOD_BENCHMARK_COMPARISONS: Methods evaluated on the same benchmark dataset.
        - CO_AUTHORSHIP_NETWORK: Authors collaborating on joint publications.
    3-Hop / Lineage Queries:
        - CITATION_CHAIN: Direct and transitive citations up to 3 hops (`Paper - CITES*1..3 -> Paper`).
"""

from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class QueryTemplateType(str, Enum):
    """
    Catalog of supported parameterized query intents.
    """
    # 1-Hop Queries
    AUTHORS_OF_PAPER = "AUTHORS_OF_PAPER"
    PAPERS_BY_AUTHOR = "PAPERS_BY_AUTHOR"
    METHODS_USED_IN_PAPER = "METHODS_USED_IN_PAPER"
    DATASETS_USED_IN_PAPER = "DATASETS_USED_IN_PAPER"
    PAPERS_IN_VENUE = "PAPERS_IN_VENUE"
    PAPERS_BY_TOPIC = "PAPERS_BY_TOPIC"

    # 2-Hop Queries
    METHOD_ANCESTRY_EXTENDS = "METHOD_ANCESTRY_EXTENDS"
    METHOD_BENCHMARK_COMPARISONS = "METHOD_BENCHMARK_COMPARISONS"
    CO_AUTHORSHIP_NETWORK = "CO_AUTHORSHIP_NETWORK"

    # 3-Hop / Transitive Queries
    CITATION_CHAIN = "CITATION_CHAIN"

    # Ego-Graph / Exploratory Fallback Queries
    EGO_NEIGHBORHOOD = "EGO_NEIGHBORHOOD"


class CypherTemplate(BaseModel):
    """
    Encapsulates a safe parameterized Cypher query and its expected parameters.
    """
    template_type: QueryTemplateType = Field(..., description="Query intent identifier")
    description: str = Field(..., description="Human-readable description of traversal purpose")
    cypher_query: str = Field(..., description="Parameterized Cypher query string with $param bindings")
    required_parameters: List[str] = Field(..., description="List of required parameter keys")
    hop_count: int = Field(default=1, description="Graph traversal hop depth")


# ==============================================================================
# Parameterized Cypher Template Catalog
# ==============================================================================
# Invariant: Every query strictly uses parameter bindings ($name) to prevent injection
# Invariant: Every query returns source_chunk_id where relationships exist for grounding
CYPHER_TEMPLATES: Dict[QueryTemplateType, CypherTemplate] = {
    # --------------------------------------------------------------------------
    # 1. 1-Hop Traversals
    # --------------------------------------------------------------------------
    QueryTemplateType.AUTHORS_OF_PAPER: CypherTemplate(
        template_type=QueryTemplateType.AUTHORS_OF_PAPER,
        description="Find researchers who authored a specific publication.",
        cypher_query=(
            "MATCH (p:Paper)-[r:AUTHORED_BY]->(a:Author) "
            "WHERE ($canonical_id <> '' AND p.id = $canonical_id) OR toLower(p.name) = toLower($paper_title) "
            "RETURN p.name AS paper_title, a.name AS author_name, r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["paper_title"],
        hop_count=1,
    ),
    QueryTemplateType.PAPERS_BY_AUTHOR: CypherTemplate(
        template_type=QueryTemplateType.PAPERS_BY_AUTHOR,
        description="Find all papers authored by a specific researcher.",
        cypher_query=(
            "MATCH (a:Author)<-[r:AUTHORED_BY]-(p:Paper) "
            "WHERE toLower(a.name) CONTAINS toLower($author_name) "
            "RETURN p.name AS paper_title, a.name AS author_name, r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["author_name"],
        hop_count=1,
    ),
    QueryTemplateType.METHODS_USED_IN_PAPER: CypherTemplate(
        template_type=QueryTemplateType.METHODS_USED_IN_PAPER,
        description="Find all methods, models, or algorithms applied in a specific paper.",
        cypher_query=(
            "MATCH (p:Paper)-[r:USES_METHOD]->(m:Method) "
            "WHERE ($canonical_id <> '' AND p.id = $canonical_id) OR toLower(p.name) = toLower($paper_title) "
            "RETURN p.name AS paper_title, m.name AS method_name, r.source_chunk_id AS source_chunk_id, r.confidence AS confidence "
            "LIMIT 25"
        ),
        required_parameters=["paper_title"],
        hop_count=1,
    ),
    QueryTemplateType.DATASETS_USED_IN_PAPER: CypherTemplate(
        template_type=QueryTemplateType.DATASETS_USED_IN_PAPER,
        description="Find benchmark datasets evaluated or trained on in a paper.",
        cypher_query=(
            "MATCH (p:Paper)-[r:USES_DATASET]->(d:Dataset) "
            "WHERE ($canonical_id <> '' AND p.id = $canonical_id) OR toLower(p.name) = toLower($paper_title) "
            "RETURN p.name AS paper_title, d.name AS dataset_name, r.source_chunk_id AS source_chunk_id, r.confidence AS confidence "
            "LIMIT 25"
        ),
        required_parameters=["paper_title"],
        hop_count=1,
    ),
    QueryTemplateType.PAPERS_IN_VENUE: CypherTemplate(
        template_type=QueryTemplateType.PAPERS_IN_VENUE,
        description="Find publications published in a specific journal, conference, or archive.",
        cypher_query=(
            "MATCH (p:Paper)-[r:PUBLISHED_IN]->(v:Venue) "
            "WHERE toLower(v.name) CONTAINS toLower($venue_name) "
            "RETURN p.name AS paper_title, v.name AS venue_name, r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["venue_name"],
        hop_count=1,
    ),
    QueryTemplateType.PAPERS_BY_TOPIC: CypherTemplate(
        template_type=QueryTemplateType.PAPERS_BY_TOPIC,
        description="Find publications categorized under a specific research topic or field.",
        cypher_query=(
            "MATCH (p:Paper)-[r:HAS_TOPIC]->(t:Topic) "
            "WHERE toLower(t.name) CONTAINS toLower($topic_name) "
            "RETURN p.name AS paper_title, t.name AS topic_name, r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["topic_name"],
        hop_count=1,
    ),

    # --------------------------------------------------------------------------
    # 2. 2-Hop Traversals
    # --------------------------------------------------------------------------
    QueryTemplateType.METHOD_ANCESTRY_EXTENDS: CypherTemplate(
        template_type=QueryTemplateType.METHOD_ANCESTRY_EXTENDS,
        description="Traverse method lineage to find architectures extended by or extending a method.",
        cypher_query=(
            "MATCH path = (m1:Method)-[r:EXTENDS|COMPARED_WITH*1..2]->(m2:Method) "
            "WHERE toLower(m1.name) CONTAINS toLower($method_name) "
            "RETURN [n IN nodes(path) | n.name] AS method_chain, "
            "[rel IN relationships(path) | rel.source_chunk_id] AS chunk_ids, "
            "length(path) AS depth "
            "LIMIT 20"
        ),
        required_parameters=["method_name"],
        hop_count=2,
    ),
    QueryTemplateType.METHOD_BENCHMARK_COMPARISONS: CypherTemplate(
        template_type=QueryTemplateType.METHOD_BENCHMARK_COMPARISONS,
        description="Find methods evaluated on the same benchmark dataset as the given method.",
        cypher_query=(
            "MATCH (p1:Paper)-[:USES_METHOD]->(m1:Method), "
            "(p1)-[r1:USES_DATASET]->(d:Dataset)<-[r2:USES_DATASET]-(p2:Paper)-[:USES_METHOD]->(m2:Method) "
            "WHERE (toLower(m1.name) CONTAINS toLower($method_name) OR toLower(p1.name) CONTAINS toLower($method_name)) "
            "  AND ($compared_method = '' OR toLower(m2.name) CONTAINS toLower($compared_method) OR toLower(p2.name) CONTAINS toLower($compared_method)) "
            "  AND m1 <> m2 "
            "RETURN DISTINCT m1.name AS source_method, d.name AS shared_dataset, m2.name AS compared_method, "
            "p1.name AS paper_1, p2.name AS paper_2, "
            "[r1.source_chunk_id, r2.source_chunk_id] AS chunk_ids "
            "LIMIT 20"
        ),
        required_parameters=["method_name"],
        hop_count=2,
    ),
    QueryTemplateType.CO_AUTHORSHIP_NETWORK: CypherTemplate(
        template_type=QueryTemplateType.CO_AUTHORSHIP_NETWORK,
        description="Find co-authors who have published papers together with a researcher.",
        cypher_query=(
            "MATCH (a1:Author)<-[:AUTHORED_BY]-(p:Paper)-[r:AUTHORED_BY]->(a2:Author) "
            "WHERE toLower(a1.name) CONTAINS toLower($author_name) AND a1 <> a2 "
            "RETURN a1.name AS author_1, a2.name AS co_author, p.name AS shared_paper, "
            "r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["author_name"],
        hop_count=2,
    ),

    # --------------------------------------------------------------------------
    # 3. 3-Hop / Transitive Traversals
    # --------------------------------------------------------------------------
    QueryTemplateType.CITATION_CHAIN: CypherTemplate(
        template_type=QueryTemplateType.CITATION_CHAIN,
        description="Traverse multi-hop relationships starting from or reaching a publication.",
        cypher_query=(
            "MATCH path = (p1:Paper)-[r:CITES|EXTENDS|COMPARED_WITH|USES_METHOD*1..3]-(p2:Paper) "
            "WHERE (($canonical_id <> '' AND p1.id = $canonical_id) OR toLower(p1.name) = toLower($paper_title)) AND p1 <> p2 "
            "RETURN [n IN nodes(path) | n.name] AS citation_path, "
            "[rel IN relationships(path) | rel.source_chunk_id] AS chunk_ids, "
            "length(path) AS depth "
            "LIMIT 20"
        ),
        required_parameters=["paper_title"],
        hop_count=3,
    ),

    # --------------------------------------------------------------------------
    # 4. Ego-Graph 1-Hop Neighborhood Fallback
    # --------------------------------------------------------------------------
    QueryTemplateType.EGO_NEIGHBORHOOD: CypherTemplate(
        template_type=QueryTemplateType.EGO_NEIGHBORHOOD,
        description="Explore immediate 1-hop connected graph neighborhood for a canonical entity.",
        cypher_query=(
            "MATCH (n)-[r]-(neighbor) "
            "WHERE ($canonical_id <> '' AND n.id = $canonical_id) OR toLower(n.name) = toLower($entity_name) "
            "RETURN n.name AS entity, type(r) AS relationship, "
            "       neighbor.name AS neighbor_name, labels(neighbor)[0] AS neighbor_type, "
            "       r.source_chunk_id AS source_chunk_id "
            "LIMIT 25"
        ),
        required_parameters=["entity_name"],
        hop_count=1,
    ),
}

