"""
Canonical Entity & Document Resolver Module (Run 3B / ADR 053).

Architecture Role:
    Part of Phase 4 (Knowledge Graph Retrieval). Sits immediately before Cypher parameter
    binding in `GraphQueryEngine`. Implements a deterministic 6-tier resolution ladder
    to resolve query entity candidates to authoritative canonical IDs and names, preventing
    unconstrained `CONTAINS` queries and parameter mismatches in Neo4j.

Inputs:
    - `requested_entity`: Surface mention string from question text or router entity detector.
    - `query_text`: Full query string for contextual disambiguation.
    - `expected_type`: Optional EntityType filter (Paper, Method, Dataset, Author, etc.).

Outputs:
    - `ResolutionResult`: Structured model containing canonical ID, canonical name, entity type,
      confidence scores, candidate set, acceptance flag, and rejection reason.

Resolution Strategy (6-Tier Ladder):
    1. Canonical ID: Exact document or node accession ID (e.g., "arxiv_2507.23581v2").
    2. Normalized arXiv ID: Regex pattern `\\b\\d{4}\\.\\d{4,5}(v\\d+)?\\b` matched against corpus.
    3. Exact Normalized Title / Name: Unicode NFKC + lowercase + punctuation stripped exact match.
    4. Curated Canonical Alias: Explicit deterministic aliases (e.g. "HeRo", "GraphSearch", "GraphRAG-R1").
    5. Controlled Token Similarity: Normalized token Jaccard similarity across known entity catalog.
    6. Ambiguity Gate & Rejection: Rejects if top_score < 0.85 OR (top_score - second_score < 0.15).
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.eval.text_norm import normalize_text
from src.graph.models import EntityType

logger = setup_logger(name="graph.canonical_resolver")

# Named constants for ambiguity & confidence thresholds
CONFIDENCE_THRESHOLD = 0.85
AMBIGUITY_DELTA_THRESHOLD = 0.15

ARXIV_ID_PATTERN = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)

# Curated alias table mapping short names / acronyms to (canonical_id, canonical_name, entity_type)
CURATED_ENTITY_ALIASES: Dict[str, Tuple[Optional[str], str, EntityType]] = {
    # Papers (with canonical arxiv paper_id)
    "graphrag-r1": ("arxiv_2507.23581v2", "GraphRAG-R1", EntityType.PAPER),
    "graphrag r1": ("arxiv_2507.23581v2", "GraphRAG-R1", EntityType.PAPER),
    "hero": ("arxiv_2603.01661v2", "HeRo", EntityType.PAPER),
    "hero framework": ("arxiv_2603.01661v2", "HeRo", EntityType.PAPER),
    "graphsearch": ("arxiv_2509.22009v2", "GraphSearch", EntityType.PAPER),
    "ace-graphrag": ("arxiv_2608.01269v2", "ACE-GraphRAG", EntityType.PAPER),
    "ace graphrag": ("arxiv_2608.01269v2", "ACE-GraphRAG", EntityType.PAPER),
    "dissecting agentic rag": ("arxiv_2606.21553v1", "Dissecting Agentic RAG: A Component Ablation for Multi-Hop QA with a Local 7B Model", EntityType.PAPER),
    "agenticragtracer": ("arxiv_2602.19127v2", "AgenticRAGTracer: A Hop-Aware Benchmark for Diagnosing Multi-Step Retrieval Reasoning in Agentic RAG", EntityType.PAPER),
    "rag vs. graphrag": ("arxiv_2502.11371v3", "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights", EntityType.PAPER),
    "rag vs graphrag": ("arxiv_2502.11371v3", "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights", EntityType.PAPER),
    "graphrag-bench": ("arxiv_2506.02404v3", "GraphRAG-Bench", EntityType.PAPER),
    "graphrag bench": ("arxiv_2506.02404v3", "GraphRAG-Bench", EntityType.PAPER),
    "when to use graphs in rag": ("arxiv_2506.05690v3", "When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation", EntityType.PAPER),
    "toward robust graphrag": ("arxiv_2603.14828v2", "Toward Robust GraphRAG: Mitigating Retrieval Drift and Hallucination from Imperfect Knowledge Graphs", EntityType.PAPER),
    "metarag": ("arxiv_2608.24214v1", "MetaRAG", EntityType.PAPER),
    "do we still need graphrag": ("arxiv_2604.09666v1", "Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems", EntityType.PAPER),
    "do we still need graphrag?": ("arxiv_2604.09666v1", "Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems", EntityType.PAPER),
    "latentrag": ("arxiv_2605.06285v1", "LatentRAG", EntityType.PAPER),
    "dyg-rag": ("arxiv_2507.13396v1", "DyG-RAG", EntityType.PAPER),
    "hvm-graphrag": ("arxiv_2607.24861v1", "HVM-GraphRAG", EntityType.PAPER),
    "plasma graphrag": ("arxiv_2604.06279v1", "Plasma GraphRAG", EntityType.PAPER),
    "dynagrag": ("arxiv_2412.18644v3", "DynaGRAG", EntityType.PAPER),
    "grag": ("arxiv_2405.16506v3", "GRAG: Graph Retrieval-Augmented Generation", EntityType.PAPER),
    "can compact language models search like agents": ("arxiv_2508.20324v4", "Can Compact Language Models Search Like Agents?", EntityType.PAPER),
    "search-r1": ("arxiv_2507.10411v1", "Search-R1", EntityType.PAPER),
    "r1-searcher": ("arxiv_2507.10411v1", "R1-Searcher", EntityType.PAPER),
    "metakgrag": ("arxiv_2508.09460v1", "MetaKGRAG", EntityType.PAPER),
    "ragsearch": ("arxiv_2604.09666v1", "RAGSearch", EntityType.PAPER),

    # Benchmarks & Datasets
    "islamicfaithqa": (None, "IslamicFaithQA", EntityType.DATASET),
    "hotpotqa": (None, "HotpotQA", EntityType.DATASET),
}


class CandidateEvaluation(BaseModel):
    """Represents a scored candidate considered during resolution."""
    canonical_id: Optional[str] = None
    canonical_name: str
    entity_type: EntityType
    score: float
    match_method: str


class ResolutionResult(BaseModel):
    """Authoritative result returned by CanonicalEntityResolver."""
    requested_entity: str
    resolved_entity: Optional[str] = None
    canonical_id: Optional[str] = None
    canonical_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    match_method: Optional[str] = None
    top_score: float = 0.0
    second_score: float = 0.0
    ambiguity_count: int = 0
    accepted: bool = False
    reason: Optional[str] = None
    candidate_set: List[CandidateEvaluation] = Field(default_factory=list)


class CanonicalEntityResolver:
    """
    Implements a 6-tier entity and document resolution ladder with strict ambiguity gates.
    """

    def __init__(self, catalog_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.catalog_path = Path(catalog_path or getattr(settings, "papers_catalog_path", "data/corpus/papers.json"))
        # Storage:
        # id -> dict (paper_id, title, norm_title)
        self._papers_by_id: Dict[str, Dict[str, Any]] = {}
        # norm_title -> dict
        self._papers_by_norm_title: Dict[str, Dict[str, Any]] = {}
        # Dynamic entities registered from Neo4j: (entity_type, norm_name) -> canonical_name
        self._registered_entities: Dict[Tuple[EntityType, str], str] = {}
        self._registered_aliases: Dict[str, Tuple[Optional[str], str, EntityType]] = dict(CURATED_ENTITY_ALIASES)
        self.resolution_audit_log: List[Dict[str, Any]] = []

        self._load_catalog()

    def _load_catalog(self) -> None:
        """Loads and indexes the document corpus catalog."""
        if not self.catalog_path.exists():
            logger.warning("Corpus catalog not found at %s", self.catalog_path)
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                papers = json.load(f)

            for p in papers:
                pid = p.get("paper_id", "")
                title = p.get("title", "")
                if not pid or not title:
                    continue
                norm_t = normalize_text(title)
                rec = {
                    "paper_id": pid,
                    "title": title,
                    "norm_title": norm_t,
                    "tokens": set(re.findall(r"\w+", norm_t)),
                }
                self._papers_by_id[pid] = rec
                self._papers_by_norm_title[norm_t] = rec

            logger.info("CanonicalEntityResolver loaded %d papers from catalog", len(self._papers_by_id))
        except Exception as exc:
            logger.error("Failed loading catalog into CanonicalEntityResolver: %s", exc)

    def register_graph_entities(self, entities: List[Tuple[str, EntityType, List[str]]]) -> None:
        """
        Registers Neo4j nodes and their aliases into the resolver index.
        Args:
            entities: List of (canonical_name, entity_type, aliases)
        """
        for cname, etype, aliases in entities:
            norm_name = normalize_text(cname)
            self._registered_entities[(etype, norm_name)] = cname
            if norm_name not in self._registered_aliases:
                # Check if this node corresponds to a known paper
                pid = self._find_paper_id_for_name(cname)
                self._registered_aliases[norm_name] = (pid, cname, etype)

            for alias in aliases:
                norm_alias = normalize_text(alias)
                if norm_alias and norm_alias not in self._registered_aliases:
                    pid = self._find_paper_id_for_name(cname)
                    self._registered_aliases[norm_alias] = (pid, cname, etype)

    def _find_paper_id_for_name(self, name: str) -> Optional[str]:
        """Maps an entity name to a paper_id if it corresponds to a catalog paper."""
        norm = normalize_text(name)
        if norm in self._papers_by_norm_title:
            return self._papers_by_norm_title[norm]["paper_id"]
        for pid, p in self._papers_by_id.items():
            if norm == normalize_text(p["title"]) or norm in normalize_text(p["title"]) or normalize_text(p["title"]) in norm:
                return pid
        return None

    @staticmethod
    def _token_jaccard(tokens1: Set[str], tokens2: Set[str]) -> float:
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0

    def resolve(
        self,
        requested_entity: str,
        query_text: str = "",
        expected_type: Optional[EntityType] = None,
    ) -> ResolutionResult:
        """
        Executes the 6-tier resolution ladder with ambiguity gating.
        """
        clean_req = requested_entity.strip()
        norm_req = normalize_text(clean_req)
        clean_query = query_text.strip()
        norm_query = normalize_text(clean_query)

        # ----------------------------------------------------------------------
        # Tier 1: Canonical Document / Node ID
        # ----------------------------------------------------------------------
        # Exact match to paper_id (e.g., "arxiv_2507.23581v2")
        pid_clean = norm_req.replace("_", ".")
        for pid in self._papers_by_id:
            if pid == clean_req or pid == pid_clean or pid.replace(".", "_") == clean_req:
                p = self._papers_by_id[pid]
                eval_cand = CandidateEvaluation(
                    canonical_id=pid,
                    canonical_name=p["title"],
                    entity_type=EntityType.PAPER,
                    score=1.0,
                    match_method="canonical_id",
                )
                res = ResolutionResult(
                    requested_entity=requested_entity,
                    resolved_entity=p["title"],
                    canonical_id=pid,
                    canonical_name=p["title"],
                    entity_type=EntityType.PAPER,
                    match_method="canonical_id",
                    top_score=1.0,
                    second_score=0.0,
                    ambiguity_count=1,
                    accepted=True,
                    candidate_set=[eval_cand],
                )
                self.resolution_audit_log.append(res.model_dump())
                return res

        # ----------------------------------------------------------------------
        # Tier 2: Normalized arXiv ID
        # ----------------------------------------------------------------------
        arxiv_match = ARXIV_ID_PATTERN.search(clean_req) or ARXIV_ID_PATTERN.search(clean_query)
        if arxiv_match:
            raw_arxiv_id = arxiv_match.group(1)
            target_pid = f"arxiv_{raw_arxiv_id}"
            if target_pid in self._papers_by_id:
                p = self._papers_by_id[target_pid]
                eval_cand = CandidateEvaluation(
                    canonical_id=target_pid,
                    canonical_name=p["title"],
                    entity_type=EntityType.PAPER,
                    score=1.0,
                    match_method="normalized_arxiv_id",
                )
                res = ResolutionResult(
                    requested_entity=requested_entity,
                    resolved_entity=p["title"],
                    canonical_id=target_pid,
                    canonical_name=p["title"],
                    entity_type=EntityType.PAPER,
                    match_method="normalized_arxiv_id",
                    top_score=1.0,
                    second_score=0.0,
                    ambiguity_count=1,
                    accepted=True,
                    candidate_set=[eval_cand],
                )
                self.resolution_audit_log.append(res.model_dump())
                return res

        # ----------------------------------------------------------------------
        # Tier 3: Exact Normalized Title / Name
        # ----------------------------------------------------------------------
        # Check catalog papers
        if norm_req in self._papers_by_norm_title:
            p = self._papers_by_norm_title[norm_req]
            eval_cand = CandidateEvaluation(
                canonical_id=p["paper_id"],
                canonical_name=p["title"],
                entity_type=EntityType.PAPER,
                score=1.0,
                match_method="exact_normalized_title",
            )
            res = ResolutionResult(
                requested_entity=requested_entity,
                resolved_entity=p["title"],
                canonical_id=p["paper_id"],
                canonical_name=p["title"],
                entity_type=EntityType.PAPER,
                match_method="exact_normalized_title",
                top_score=1.0,
                second_score=0.0,
                ambiguity_count=1,
                accepted=True,
                candidate_set=[eval_cand],
            )
            self.resolution_audit_log.append(res.model_dump())
            return res

        # Check registered entities from graph
        for (etype, nname), cname in self._registered_entities.items():
            if expected_type and etype != expected_type:
                continue
            if norm_req == nname:
                pid = self._find_paper_id_for_name(cname)
                eval_cand = CandidateEvaluation(
                    canonical_id=pid,
                    canonical_name=cname,
                    entity_type=etype,
                    score=1.0,
                    match_method="exact_normalized_title",
                )
                res = ResolutionResult(
                    requested_entity=requested_entity,
                    resolved_entity=cname,
                    canonical_id=pid,
                    canonical_name=cname,
                    entity_type=etype,
                    match_method="exact_normalized_title",
                    top_score=1.0,
                    second_score=0.0,
                    ambiguity_count=1,
                    accepted=True,
                    candidate_set=[eval_cand],
                )
                self.resolution_audit_log.append(res.model_dump())
                return res

        # ----------------------------------------------------------------------
        # Tier 4: Curated Canonical Alias Table
        # ----------------------------------------------------------------------
        if norm_req in self._registered_aliases:
            pid, cname, etype = self._registered_aliases[norm_req]
            if not expected_type or etype == expected_type:
                eval_cand = CandidateEvaluation(
                    canonical_id=pid,
                    canonical_name=cname,
                    entity_type=etype,
                    score=1.0,
                    match_method="alias_table",
                )
                res = ResolutionResult(
                    requested_entity=requested_entity,
                    resolved_entity=cname,
                    canonical_id=pid,
                    canonical_name=cname,
                    entity_type=etype,
                    match_method="alias_table",
                    top_score=1.0,
                    second_score=0.0,
                    ambiguity_count=1,
                    accepted=True,
                    candidate_set=[eval_cand],
                )
                self.resolution_audit_log.append(res.model_dump())
                return res

        # ----------------------------------------------------------------------
        # Tier 5: Controlled Token Similarity (Jaccard >= 0.85)
        # ----------------------------------------------------------------------
        req_tokens = set(re.findall(r"\w+", norm_req))
        scored_candidates: List[CandidateEvaluation] = []

        # Compare against papers
        for pid, p in self._papers_by_id.items():
            if expected_type and expected_type != EntityType.PAPER:
                continue
            sim = self._token_jaccard(req_tokens, p["tokens"])
            if sim >= 0.50:  # Collect candidate for ambiguity detection
                scored_candidates.append(
                    CandidateEvaluation(
                        canonical_id=pid,
                        canonical_name=p["title"],
                        entity_type=EntityType.PAPER,
                        score=round(sim, 4),
                        match_method="controlled_token_similarity",
                    )
                )

        # Compare against registered graph entities
        for (etype, nname), cname in self._registered_entities.items():
            if expected_type and etype != expected_type:
                continue
            ent_tokens = set(re.findall(r"\w+", nname))
            sim = self._token_jaccard(req_tokens, ent_tokens)
            if sim >= 0.50:
                pid = self._find_paper_id_for_name(cname)
                scored_candidates.append(
                    CandidateEvaluation(
                        canonical_id=pid,
                        canonical_name=cname,
                        entity_type=etype,
                        score=round(sim, 4),
                        match_method="controlled_token_similarity",
                    )
                )

        # Deduplicate candidates by canonical_name
        seen_names: Set[str] = set()
        unique_cands: List[CandidateEvaluation] = []
        for c in sorted(scored_candidates, key=lambda x: -x.score):
            if c.canonical_name not in seen_names:
                seen_names.add(c.canonical_name)
                unique_cands.append(c)

        # Sort descending by score
        unique_cands.sort(key=lambda x: -x.score)

        top_score = unique_cands[0].score if unique_cands else 0.0
        second_score = unique_cands[1].score if len(unique_cands) > 1 else 0.0

        # ----------------------------------------------------------------------
        # Tier 6: Ambiguity Gate & Rejection
        # ----------------------------------------------------------------------
        if not unique_cands:
            res = ResolutionResult(
                requested_entity=requested_entity,
                accepted=False,
                reason="no_candidates",
                top_score=0.0,
                second_score=0.0,
                ambiguity_count=0,
                candidate_set=[],
            )
            self.resolution_audit_log.append(res.model_dump())
            return res

        # Rejection Rule: top_score - second_score < 0.15 (ambiguous tie)
        if len(unique_cands) > 1 and (top_score - second_score < AMBIGUITY_DELTA_THRESHOLD):
            res = ResolutionResult(
                requested_entity=requested_entity,
                accepted=False,
                reason="ambiguous",
                top_score=top_score,
                second_score=second_score,
                ambiguity_count=len(unique_cands),
                candidate_set=unique_cands[:5],
            )
            self.resolution_audit_log.append(res.model_dump())
            return res

        # Rejection Rule: top_score < 0.85
        if top_score < CONFIDENCE_THRESHOLD:
            res = ResolutionResult(
                requested_entity=requested_entity,
                accepted=False,
                reason="low_confidence",
                top_score=top_score,
                second_score=second_score,
                ambiguity_count=len(unique_cands),
                candidate_set=unique_cands[:5],
            )
            self.resolution_audit_log.append(res.model_dump())
            return res

        # Qualified unambiguous winner
        winner = unique_cands[0]
        res = ResolutionResult(
            requested_entity=requested_entity,
            resolved_entity=winner.canonical_name,
            canonical_id=winner.canonical_id,
            canonical_name=winner.canonical_name,
            entity_type=winner.entity_type,
            match_method=winner.match_method,
            top_score=winner.score,
            second_score=second_score,
            ambiguity_count=len(unique_cands),
            accepted=True,
            candidate_set=unique_cands[:5],
        )
        self.resolution_audit_log.append(res.model_dump())
        return res
