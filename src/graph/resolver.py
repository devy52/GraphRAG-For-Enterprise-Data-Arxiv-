"""
Entity Resolution & Deduplication Module.

Architecture Role:
    Part of Phase 2 (Knowledge Graph Ingestion). Intercepts extracted raw triples from
    `GraphExtractor` before they reach `Neo4jWriter`. Ensures that different surface forms
    of the same underlying real-world entity (e.g. "RAG", "Retrieval-Augmented Generation",
    "RAG architecture") resolve to a single canonical graph node with aggregated aliases.

Inputs:
    - Raw `ExtractedFact` triples with unnormalized surface strings.
    - Entity types (`EntityType` enum).

Outputs:
    - Resolved `ExtractedFact` triples with canonicalized entity names.
    - `ResolvedEntity` models containing canonical name, entity type, embedding, and alias list.

Resolution Strategy (Multi-Stage Cascade):
    1. Lexical Normalization: Strips quotes, excess whitespace, and trailing punctuation.
    2. Exact Case-Insensitive / Alias Match: Checks against existing registered nodes and aliases.
    3. Token Jaccard Match (Threshold >= 0.85): Catches token permutations and minor phrasing variants.
    4. Dense Vector Cosine Similarity (Threshold >= 0.88): Discovers semantic synonyms and acronyms
       via embeddings.
    5. Registry Insertion: If no match qualifies, registers a new canonical entity.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from openai import AsyncOpenAI

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.models import EntityType, ExtractedFact, ResolvedEntity

logger = setup_logger(name="graph.resolver")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
SIMILARITY_THRESHOLD = 0.88    # Cosine similarity threshold for merging entity mentions
LEXICAL_THRESHOLD = 0.85       # Token Jaccard similarity threshold for lexical clustering


class EntityResolver:
    """
    Normalizes, deduplicates, and resolves extracted entity mentions to canonical entities.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key or "sk-dummy-key-for-test",
        )
        # Registry mapping: (entity_type, canonical_name) -> ResolvedEntity
        self.registry: Dict[Tuple[EntityType, str], ResolvedEntity] = {}

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Cleans and normalizes surface strings:
        - Strips whitespace and surrounding quotation marks / punctuation.
        - Standardizes internal whitespace to single spaces.
        """
        cleaned = name.strip().strip("\"'.,;:")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    @staticmethod
    def _lexical_similarity(str1: str, str2: str) -> float:
        """
        Computes fast normalized token Jaccard similarity between two strings.
        Jaccard = |Tokens(S1) ∩ Tokens(S2)| / |Tokens(S1) ∪ Tokens(S2)|
        """
        s1 = set(re.findall(r"\w+", str1.lower()))
        s2 = set(re.findall(r"\w+", str2.lower()))
        if not s1 or not s2:
            return 0.0
        intersection = len(s1 & s2)
        union = len(s1 | s2)
        return intersection / union

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generates dense text embedding for semantic similarity matching.
        Returns None if API key is not configured or in offline test mode.
        """
        if not self.settings.llm_api_key:
            return None
        try:
            res = await self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=text,
            )
            return res.data[0].embedding
        except Exception as exc:
            logger.debug("Embedding call skipped/failed during resolution: %s", exc)
            return None

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Computes cosine similarity between two float vectors: (A . B) / (||A|| * ||B||).
        """
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = sum(a * a for a in vec1) ** 0.5
        norm_b = sum(b * b for b in vec2) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def resolve_entity(self, raw_name: str, entity_type: EntityType) -> ResolvedEntity:
        """
        Resolves a single entity mention against the in-memory canonical registry.

        Cascade Pipeline:
        1. Normalization: Clean punctuation and whitespace.
        2. Exact Match: Match against canonical names or existing aliases.
        3. Lexical Jaccard: Match partial token overlap (>= 0.85).
        4. Dense Embedding Cosine: Match semantic synonyms (>= 0.88).
        5. Fallback: Register as a new canonical entity.
        """
        # ----------------------------------------------------------------------
        # Step 1: Lexical Cleanup & Sanitization
        # ----------------------------------------------------------------------
        normalized = self.normalize_name(raw_name)
        if not normalized:
            normalized = "Unknown"

        # ----------------------------------------------------------------------
        # Step 2: Exact Canonical or Alias Match Check
        # ----------------------------------------------------------------------
        for (etype, cname), existing in self.registry.items():
            if etype == entity_type:
                if normalized.lower() == cname.lower() or any(
                    normalized.lower() == alias.lower() for alias in existing.aliases
                ):
                    if raw_name not in existing.aliases and raw_name != existing.canonical_name:
                        existing.aliases.append(raw_name)
                    return existing

        # ----------------------------------------------------------------------
        # Step 3: Fast Token Jaccard Similarity Match
        # ----------------------------------------------------------------------
        for (etype, cname), existing in self.registry.items():
            if etype == entity_type:
                lex_sim = self._lexical_similarity(normalized, cname)
                if lex_sim >= LEXICAL_THRESHOLD:
                    logger.debug("Lexical match: '%s' -> canonical '%s' (sim=%.2f)", normalized, cname, lex_sim)
                    if raw_name not in existing.aliases:
                        existing.aliases.append(raw_name)
                    return existing

        # ----------------------------------------------------------------------
        # Step 4: Dense Vector Cosine Similarity Match
        # ----------------------------------------------------------------------
        candidate_embedding = await self.get_embedding(normalized)
        if candidate_embedding:
            best_match: Optional[ResolvedEntity] = None
            best_score = 0.0

            for (etype, cname), existing in self.registry.items():
                if etype == entity_type and existing.embedding:
                    score = self._cosine_similarity(candidate_embedding, existing.embedding)
                    if score > best_score:
                        best_score = score
                        best_match = existing

            if best_match and best_score >= SIMILARITY_THRESHOLD:
                logger.debug(
                    "Embedding match: '%s' -> canonical '%s' (score=%.2f)",
                    normalized,
                    best_match.canonical_name,
                    best_score,
                )
                if raw_name not in best_match.aliases:
                    best_match.aliases.append(raw_name)
                return best_match

        # ----------------------------------------------------------------------
        # Step 5: Register New Canonical Entity
        # ----------------------------------------------------------------------
        resolved = ResolvedEntity(
            canonical_name=normalized,
            entity_type=entity_type,
            aliases=[raw_name] if raw_name != normalized else [],
            embedding=candidate_embedding,
        )
        self.registry[(entity_type, normalized)] = resolved
        return resolved

    async def resolve_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        """
        Resolves both source and target entities across a collection of extracted facts,
        replacing surface mention strings with their canonical resolved names.

        Args:
            facts: List of raw ExtractedFact models.

        Returns:
            List of ExtractedFact models with canonical names.
        """
        # Step 1: Initialize collection for canonicalized fact records
        resolved_facts: List[ExtractedFact] = []
        
        # Step 2: Iterate through each extracted fact triple
        for fact in facts:
            # Step 3: Progressively resolve source entity mention against canonical registry
            source_res = await self.resolve_entity(fact.source_name, fact.source_type)
            # Step 4: Progressively resolve target entity mention against canonical registry
            target_res = await self.resolve_entity(fact.target_name, fact.target_type)

            # Step 5: Reconstruct ExtractedFact using canonical names while retaining chunk attribution
            updated_fact = ExtractedFact(
                source_name=source_res.canonical_name,
                source_type=fact.source_type,
                relation=fact.relation,
                target_name=target_res.canonical_name,
                target_type=fact.target_type,
                source_chunk_id=fact.source_chunk_id,
                confidence=fact.confidence,
            )
            resolved_facts.append(updated_fact)

        logger.info(
            "Resolved %d facts into %d unique canonical entities",
            len(resolved_facts),
            len(self.registry),
        )
        return resolved_facts

    async def resolve_and_link(
        self, facts: List[ExtractedFact]
    ) -> Tuple[List[ResolvedEntity], List[ExtractedFact]]:
        """
        Resolves entity mentions across facts and returns both the unique ResolvedEntity
        models and the canonicalized ExtractedFact triples for graph persistence.

        Args:
            facts: List of raw ExtractedFact models.

        Returns:
            Tuple of (distinct resolved entities touched in this batch, canonicalized facts).
        """
        resolved_facts: List[ExtractedFact] = []
        batch_entities: Dict[Tuple[EntityType, str], ResolvedEntity] = {}

        for fact in facts:
            source_res = await self.resolve_entity(fact.source_name, fact.source_type)
            target_res = await self.resolve_entity(fact.target_name, fact.target_type)

            batch_entities[(source_res.entity_type, source_res.canonical_name)] = source_res
            batch_entities[(target_res.entity_type, target_res.canonical_name)] = target_res

            updated_fact = ExtractedFact(
                source_name=source_res.canonical_name,
                source_type=fact.source_type,
                relation=fact.relation,
                target_name=target_res.canonical_name,
                target_type=fact.target_type,
                source_chunk_id=fact.source_chunk_id,
                confidence=fact.confidence,
            )
            resolved_facts.append(updated_fact)

        logger.info(
            "resolve_and_link: Processed %d facts into %d unique batch entities",
            len(resolved_facts),
            len(batch_entities),
        )
        return list(batch_entities.values()), resolved_facts

