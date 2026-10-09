"""
Bounded LangGraph Evidence Refinement Module.

Architecture Role:
    Part of Phase 5 (Question Router & Retrieval Refinement; ADR 070).
    Implements a bounded, single-pass LangGraph StateGraph that activates ONLY when an
    evidence gap is detected (i.e. a salient ontology entity or target document from
    the enterprise corpus is absent from initial retrieval context).
    Bypassed entirely for ~54% of queries that have complete evidence or are out-of-scope.

Inputs:
    - User query string.
    - Initial `graph_facts` (List[str]) produced by GraphQueryEngine.
    - Initial `retrieved_chunks` (List[VectorSearchResult]) from VectorStore.

Outputs:
    - Structured refinement dictionary containing:
        - `refinement_activated` (bool): True if LangGraph pass executed.
        - `missing_entities` (List[str]): Corpus entities missing from initial context.
        - `missing_doc_ids` (List[str]): Target paper IDs missing from initial chunks.
        - `refined_graph_facts` (List[str]): Budget-capped targeted graph facts.
        - `refined_chunks` (List[VectorSearchResult]): Budget-capped targeted text passages.
        - `latencies` (Dict[str, float]): Per-node execution timing in milliseconds.

Design Decisions:
    - Zero-LLM Gap Detection: Uses deterministic ontology and catalog lookups (<1ms)
      rather than an expensive LLM router roundtrip (saving 1.5s - 2.5s network transit).
    - Strict Resource Caps: Bounds graph facts to <= max_refined_facts (default 3)
      and vector chunks to <= max_refined_chunks (default 2) to prevent prompt bloat.
    - Full Provenance Integrity: All refined statements retain chunk foreign keys and
      all refined chunks are registered in cited_chunk_ids for AST validation.
    - Linear 3-Node Topology: START -> isolate_gap -> targeted_retrieval -> merge_evidence -> END.
      Avoids non-deterministic cyclic loops that inflate latency.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.query_engine import GraphQueryEngine
from src.graph.templates import QueryTemplateType
from src.router.metadata_resolver import MetadataResolver
from src.vector.indexer import VectorStore
from src.vector.models import VectorSearchResult

logger = setup_logger(name="router.refiner")


class RefinementState(TypedDict, total=False):
    """
    State schema for the bounded 1-pass LangGraph evidence refinement graph.
    """
    query: str
    missing_entities: List[str]
    missing_doc_ids: List[str]
    initial_graph_facts: List[str]
    initial_chunk_ids: List[str]
    refined_graph_facts: List[str]
    refined_chunks: List[VectorSearchResult]
    latencies: Dict[str, float]


class EvidenceRefiner:
    """
    Bounded LangGraph Evidence Refinement Engine.

    Coordinates zero-overhead gap detection, targeted ego-neighborhood expansion,
    doc-filtered passage recovery, and budget-capped evidence merging.
    """

    def __init__(
        self,
        query_engine: Optional[GraphQueryEngine] = None,
        vector_store: Optional[VectorStore] = None,
        metadata_resolver: Optional[MetadataResolver] = None,
        max_refined_facts: Optional[int] = None,
        max_refined_chunks: Optional[int] = None,
    ) -> None:
        """
        Initializes the EvidenceRefiner and compiles the LangGraph StateGraph.

        Args:
            query_engine: GraphQueryEngine for Neo4j ego-neighborhood traversals.
            vector_store: VectorStore for doc-filtered pgvector similarity searches.
            metadata_resolver: MetadataResolver for paper catalog lookup.
            max_refined_facts: Maximum refined graph facts to add (default 3).
            max_refined_chunks: Maximum refined vector passages to add (default 2).
        """
        self.settings = get_settings()
        self.query_engine = query_engine or GraphQueryEngine()
        self.vector_store = vector_store or VectorStore()
        self.metadata_resolver = metadata_resolver or MetadataResolver()

        self.max_refined_facts = (
            max_refined_facts
            if max_refined_facts is not None
            else getattr(self.settings, "max_refined_facts", 3)
        )
        self.max_refined_chunks = (
            max_refined_chunks
            if max_refined_chunks is not None
            else getattr(self.settings, "max_refined_chunks", 2)
        )

        # Compile the bounded 1-pass refinement StateGraph
        self.refinement_graph = self._build_refinement_graph()

    # --------------------------------------------------------------------------
    # Evidence Gap Detector (Heuristic, zero-LLM overhead)
    #
    # Architecture Rationale:
    #   Why zero-LLM? Using an LLM-based "sufficiency judge" or "query reformulation"
    #   agent introduces an extra 1,500ms - 2,500ms network round-trip on EVERY single query,
    #   severely penalizing the 54% of queries that already have complete evidence.
    #   Instead, this heuristic checks whether named entities and paper IDs present in the
    #   user question were omitted from the retrieved context. This lookup takes <1ms, is
    #   100% deterministic, and introduces 0 extra API cost.
    # --------------------------------------------------------------------------
    def detect_evidence_gap(
        self,
        query: str,
        graph_facts: List[str],
        retrieved_chunks: List[VectorSearchResult],
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Detects whether initial retrieval missed a salient question entity or target document.

        Mechanism:
            1. Scans query for entities present in the canonical Neo4j graph registry.
            2. Scans query for paper IDs/titles present in the metadata resolver catalog.
            3. Checks whether these entities or documents appear in initial graph facts
               or retrieved chunk text.
            4. If any question entity or target document is absent, triggers refinement.

        Returns:
            (has_gap, missing_entities, missing_doc_ids)
        """
        q_lower = query.lower()

        # Step 1: Identify query entities present in the canonical graph registry.
        # Rationale: Only check entities known to exist in our corpus ontology to avoid false
        # alarms on generic out-of-scope vocabulary.
        corpus_entities: List[str] = []
        if hasattr(self.query_engine, "identify_entities_in_text"):
            found_ents = self.query_engine.identify_entities_in_text(query)
            for c_ent, _ in found_ents:
                corpus_entities.append(c_ent)

        # Step 2: Identify target papers mentioned in query via catalog metadata.
        # Rationale: Queries often reference papers by title fragment, arXiv ID, or acronym.
        # If the query asks for a specific paper, its chunks MUST be in the context.
        target_doc_ids: List[str] = []
        if self.metadata_resolver and hasattr(self.metadata_resolver, "_indexed_papers"):
            for p in self.metadata_resolver._indexed_papers:
                pid = p.get("paper_id", "") if isinstance(p, dict) else getattr(p, "paper_id", "")
                title = (p.get("title", "") if isinstance(p, dict) else getattr(p, "title", "")).lower()
                short_title = title.split(":")[0].strip()
                clean_pid = pid.replace(".", "_")
                raw_pid = pid.lower()
                if (
                    (clean_pid and clean_pid.lower() in q_lower)
                    or (raw_pid and raw_pid in q_lower)
                    or (title and title in q_lower)
                    or (len(short_title) > 10 and short_title in q_lower)
                ):
                    target_doc_ids.append(clean_pid)
                    target_doc_ids.append(pid)

        # Step 3: Build search text from initial context (graph statements + chunk text)
        context_text = " ".join(graph_facts) + " " + " ".join(c.text for c in retrieved_chunks)
        context_text_lower = context_text.lower()
        retrieved_chunk_ids = {c.chunk_id for c in retrieved_chunks}
        retrieved_doc_ids = {
            cid.replace("chunk_", "").rsplit("_", 1)[0].replace(".", "_")
            for cid in retrieved_chunk_ids
        } | {
            cid.replace("chunk_", "").rsplit("_", 1)[0]
            for cid in retrieved_chunk_ids
        }

        # Step 4: Verify entity coverage
        missing_entities: List[str] = []
        for ent in corpus_entities:
            ent_lower = ent.lower()
            if ent_lower not in context_text_lower:
                missing_entities.append(ent)

        # Step 5: Verify document coverage
        missing_doc_ids: List[str] = []
        for t_doc in target_doc_ids:
            if t_doc not in retrieved_doc_ids and t_doc.replace(".", "_") not in retrieved_doc_ids:
                missing_doc_ids.append(t_doc)

        has_gap = bool(missing_entities or missing_doc_ids)
        return has_gap, missing_entities, missing_doc_ids

    # --------------------------------------------------------------------------
    # LangGraph Refinement Nodes (Bounded 1-pass)
    #
    # Architecture Rationale:
    #   Why 3 linear nodes instead of a cyclical loop?
    #   The standalone LangGraph implementation evaluated in Phase 34 had an iterative
    #   self-correction loop that re-synthesized upon validation failure. That caused
    #   P50 latency to balloon to 37.1 seconds.
    #   Here, we decouple refinement into a single deterministic 1-pass retrieval expansion:
    #     Node 1: Isolate specific entity/document gaps
    #     Node 2: Targeted ego-neighborhood graph expansion & doc-filtered vector lookup
    #     Node 3: Deduplicate, budget-cap, and merge evidence
    #   This keeps median refinement overhead to only ~398ms (~6.7% of total latency).
    # --------------------------------------------------------------------------
    async def isolate_gap_node(self, state: RefinementState) -> Dict[str, Any]:
        """
        Node 1: Confirms missing entities and documents to target.
        """
        t0 = time.time()
        m_ents = state.get("missing_entities", [])
        m_docs = state.get("missing_doc_ids", [])
        logger.info(
            "LangGraph Refinement Node 1: Targeted gap detected: entities=%s, docs=%s",
            m_ents, m_docs,
        )
        latencies = dict(state.get("latencies", {}))
        latencies["isolate_gap_ms"] = round((time.time() - t0) * 1000.0, 2)
        return {"latencies": latencies}

    async def targeted_retrieval_node(self, state: RefinementState) -> Dict[str, Any]:
        """
        Node 2: Targeted ego-neighborhood graph expansion and filtered vector lookup.

        Logic:
            1. For missing entities: traverses immediate Neo4j 1-hop ego-neighborhood
               (EGO_NEIGHBORHOOD template) to fetch connected relations and facts.
            2. For missing documents: executes vector similarity search filtered
               specifically to chunks belonging to those document IDs.
        """
        t0 = time.time()
        query = state["query"]
        missing_entities = state.get("missing_entities", [])
        missing_doc_ids = state.get("missing_doc_ids", [])

        refined_facts: List[str] = []
        refined_chunks: List[VectorSearchResult] = []

        # 1. Targeted Graph Ego-Neighborhood for missing entities (capped at first 2 entities)
        # Prevents fan-out explosion on questions with many entity mentions.
        for ent in missing_entities[:2]:
            try:
                g_res = await self.query_engine.execute_query(
                    QueryTemplateType.EGO_NEIGHBORHOOD,
                    {"entity_name": ent},
                )
                if g_res and g_res.formatted_statements:
                    refined_facts.extend(g_res.formatted_statements)
            except Exception as exc:
                logger.warning("Targeted ego-neighborhood failed for '%s': %s", ent, exc)

        # 2. Targeted Vector Retrieval for missing documents
        # Directly fetches passages from omitted target paper, recovering
        # evidence that global top-k vector search pushed out of the candidate pool.
        filter_docs = None
        if missing_doc_ids:
            filter_docs = list(set(
                missing_doc_ids
                + [d.replace("_", ".") for d in missing_doc_ids]
                + [d.replace(".", "_") for d in missing_doc_ids]
            ))
        try:
            chunks = await self.vector_store.similarity_search(
                query,
                top_k=self.max_refined_chunks + 2,
                filter_document_ids=filter_docs,
            )
            refined_chunks.extend(chunks)
        except Exception as exc:
            logger.warning("Targeted vector retrieval failed: %s", exc)

        latencies = dict(state.get("latencies", {}))
        latencies["targeted_retrieval_ms"] = round((time.time() - t0) * 1000.0, 2)

        return {
            "refined_graph_facts": refined_facts,
            "refined_chunks": refined_chunks,
            "latencies": latencies,
        }

    async def merge_evidence_node(self, state: RefinementState) -> Dict[str, Any]:
        """
        Node 3: Deduplicates, applies strict budgets, and formats refined evidence.

        Why strict caps?
            - max_refined_facts (default 3): keeps prompt concise and prevents LLM distraction.
            - max_refined_chunks (default 2): restricts token expansion while supplying
              the critical missing grounding paragraph.
        """
        t0 = time.time()
        initial_facts = set(state.get("initial_graph_facts", []))
        initial_cids = set(state.get("initial_chunk_ids", []))

        candidate_facts = state.get("refined_graph_facts", [])
        candidate_chunks = state.get("refined_chunks", [])

        # Deduplicate & Budget Facts (<= max_refined_facts)
        new_facts: List[str] = []
        for fact in candidate_facts:
            if fact not in initial_facts and fact not in new_facts:
                new_facts.append(fact)
                if len(new_facts) >= self.max_refined_facts:
                    break

        # Deduplicate & Budget Chunks (<= max_refined_chunks)
        new_chunks: List[VectorSearchResult] = []
        for chunk in candidate_chunks:
            if chunk.chunk_id not in initial_cids and chunk.chunk_id not in {c.chunk_id for c in new_chunks}:
                new_chunks.append(chunk)
                if len(new_chunks) >= self.max_refined_chunks:
                    break

        latencies = dict(state.get("latencies", {}))
        latencies["merge_evidence_ms"] = round((time.time() - t0) * 1000.0, 2)

        return {
            "refined_graph_facts": new_facts,
            "refined_chunks": new_chunks,
            "latencies": latencies,
        }

    def _build_refinement_graph(self):
        """
        Compiles the bounded 3-node LangGraph StateGraph.
        """
        builder = StateGraph(RefinementState)
        builder.add_node("isolate_gap_node", self.isolate_gap_node)
        builder.add_node("targeted_retrieval_node", self.targeted_retrieval_node)
        builder.add_node("merge_evidence_node", self.merge_evidence_node)

        builder.add_edge(START, "isolate_gap_node")
        builder.add_edge("isolate_gap_node", "targeted_retrieval_node")
        builder.add_edge("targeted_retrieval_node", "merge_evidence_node")
        builder.add_edge("merge_evidence_node", END)

        return builder.compile()

    # --------------------------------------------------------------------------
    # Public Execution Method
    # --------------------------------------------------------------------------
    async def refine(
        self,
        query: str,
        initial_graph_facts: List[str],
        initial_chunks: List[VectorSearchResult],
    ) -> Dict[str, Any]:
        """
        Executes bounded evidence refinement if an evidence gap is detected.

        Args:
            query: User natural language question.
            initial_graph_facts: Facts retrieved during primary retrieval pass.
            initial_chunks: Text chunks retrieved during primary retrieval pass.

        Returns:
            Dictionary with refinement outcome, extra facts, extra chunks, and latencies.
        """
        t0 = time.time()
        has_gap, missing_ents, missing_docs = self.detect_evidence_gap(
            query=query,
            graph_facts=initial_graph_facts,
            retrieved_chunks=initial_chunks,
        )

        if not has_gap:
            return {
                "refinement_activated": False,
                "missing_entities": [],
                "missing_doc_ids": [],
                "refined_graph_facts": [],
                "refined_chunks": [],
                "latencies": {"gap_check_ms": round((time.time() - t0) * 1000.0, 2)},
            }

        logger.info(
            "Evidence gap detected for query '%s' (ents=%s, docs=%s). Invoking LangGraph refinement.",
            query, missing_ents, missing_docs,
        )

        init_state: RefinementState = {
            "query": query,
            "missing_entities": missing_ents,
            "missing_doc_ids": missing_docs,
            "initial_graph_facts": list(initial_graph_facts),
            "initial_chunk_ids": [c.chunk_id for c in initial_chunks],
            "latencies": {},
        }

        refinement_output = await self.refinement_graph.ainvoke(init_state)
        latencies = dict(refinement_output.get("latencies", {}))
        latencies["langgraph_refinement_total_ms"] = round((time.time() - t0) * 1000.0, 2)

        return {
            "refinement_activated": True,
            "missing_entities": missing_ents,
            "missing_doc_ids": missing_docs,
            "refined_graph_facts": refinement_output.get("refined_graph_facts", []),
            "refined_chunks": refinement_output.get("refined_chunks", []),
            "latencies": latencies,
        }
