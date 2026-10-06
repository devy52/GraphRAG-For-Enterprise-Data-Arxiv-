"""
Graph Data Models & Fixed Ontology Definitions.

Architecture Role:
    Part of Phase 2 (Knowledge Graph Ingestion). Codifies the strict ontology rules defined
    in `Docs/ONTOLOGY.md` into Pydantic models and Python Enums. Restricts LLM extraction
    to authorized entity and relationship types, preventing arbitrary hallucinated graph schemas.

Ontology Elements:
    - Entity Types (7): Paper, Author, Institution, Venue, Topic, Dataset, Method.
    - Relationship Types (9): CITES, AUTHORED_BY, AFFILIATED_WITH, PUBLISHED_IN,
      HAS_TOPIC, USES_DATASET, USES_METHOD, EXTENDS, COMPARED_WITH.
    - Domain Models: `ExtractedFact`, `ExtractionPayload`, `ResolvedEntity`.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """
    Allowed Entity Types from Docs/ONTOLOGY.md (5-10 targeted).
    Restricts extraction to a well-defined domain schema.
    """
    PAPER = "Paper"
    AUTHOR = "Author"
    INSTITUTION = "Institution"
    VENUE = "Venue"
    TOPIC = "Topic"
    DATASET = "Dataset"
    METHOD = "Method"


class RelationType(str, Enum):
    """
    Allowed Relationship Types from Docs/ONTOLOGY.md (8-15 targeted).
    Defines directed semantic predicates connecting ontology entities.
    """
    CITES = "CITES"                     # Paper -> Paper
    AUTHORED_BY = "AUTHORED_BY"         # Paper -> Author
    AFFILIATED_WITH = "AFFILIATED_WITH" # Author -> Institution
    PUBLISHED_IN = "PUBLISHED_IN"       # Paper -> Venue
    HAS_TOPIC = "HAS_TOPIC"             # Paper -> Topic
    USES_DATASET = "USES_DATASET"       # Paper -> Dataset
    USES_METHOD = "USES_METHOD"         # Paper -> Method
    EXTENDS = "EXTENDS"                 # Method -> Method
    COMPARED_WITH = "COMPARED_WITH"     # Method -> Method


class ExtractedFact(BaseModel):
    """
    Represents a single atomic fact extracted from a document chunk by the LLM.
    """
    source_name: str = Field(..., description="Name or title of the source entity")
    source_type: EntityType = Field(..., description="Ontology type of the source entity")
    relation: RelationType = Field(..., description="Ontology predicate linking source to target")
    target_name: str = Field(..., description="Name or title of the target entity")
    target_type: EntityType = Field(..., description="Ontology type of the target entity")
    source_chunk_id: str = Field(..., description="Foreign key linking to the source DocumentChunk")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)")


class ExtractionPayload(BaseModel):
    """
    Pydantic schema passed for LLM structured output validation.
    """
    facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="List of verified factual triples extracted from the passage",
    )


class ResolvedEntity(BaseModel):
    """
    Represents a canonical entity node in Neo4j after deduplication and alias resolution.
    """
    canonical_name: str = Field(..., description="Primary normalized name for the entity")
    entity_type: EntityType = Field(..., description="Ontology entity type")
    aliases: List[str] = Field(default_factory=list, description="List of recognized alternate names or surface forms")
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding of canonical name for similarity matching")
