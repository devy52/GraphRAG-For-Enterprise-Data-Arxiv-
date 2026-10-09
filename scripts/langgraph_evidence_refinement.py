"""
Hybrid Phase 32B Champion with Bounded LangGraph Evidence-Refinement Pass.

Architecture Role:
    Preserves the fast, deterministic Phase 32B champion RetrievalCoordinator as the
    primary retrieval engine (~80% of queries take the fast path). Activates a single,
    bounded LangGraph StateGraph refinement pass ONLY when an evidence gap is detected
    (a salient named entity or target document from the corpus is missing from initial context).

    Refactored in ADR 070 to import the reusable application implementation from
    `src.router.refiner.EvidenceRefiner` and `src.router.coordinator.RetrievalCoordinator`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.query_engine import GraphQueryEngine
from src.router.coordinator import RetrievalCoordinator
from src.router.models import RetrievalContext, RouteDecision
from src.router.refiner import EvidenceRefiner, RefinementState
from src.synthesis.synthesizer import AnswerSynthesizer
from src.vector.indexer import VectorStore
from src.vector.models import VectorSearchResult

logger = setup_logger(name="langgraph.evidence_refinement")

# Re-export RefinementState and EvidenceRefiner for backwards compatibility
__all__ = [
    "RefinementState",
    "EvidenceRefiner",
    "ChampionWithLangGraphRefinement",
]


class ChampionWithLangGraphRefinement:
    """
    32B Champion Coordinator + Conditional 1-Pass LangGraph Evidence Refinement.
    Delegates retrieval and refinement orchestration to core application modules in src/.
    """

    def __init__(
        self,
        coordinator: Optional[RetrievalCoordinator] = None,
        synthesizer: Optional[AnswerSynthesizer] = None,
        max_refined_facts: int = 3,
        max_refined_chunks: int = 2,
    ) -> None:
        self.settings = get_settings()
        self.max_refined_facts = max_refined_facts
        self.max_refined_chunks = max_refined_chunks

        # If coordinator is not provided, configure 32B champion with evidence refinement enabled
        self.coordinator = coordinator or RetrievalCoordinator(
            enable_graph_passage_hydration=True,
            enable_adaptive_hydration=False,  # Frozen champion: static cap=3
            max_graph_hydrated_passages=3,
            enable_evidence_refinement=True,
            max_refined_facts=self.max_refined_facts,
            max_refined_chunks=self.max_refined_chunks,
        )
        self.synthesizer = synthesizer or AnswerSynthesizer()
        self.query_engine: GraphQueryEngine = self.coordinator.query_engine
        self.vector_store: VectorStore = self.coordinator.vector_store

    @property
    def refiner(self) -> EvidenceRefiner:
        """Accesses the coordinator's underlying EvidenceRefiner."""
        return self.coordinator._get_refiner()

    @property
    def refinement_graph(self):
        """Accesses the compiled StateGraph for inspection or direct execution."""
        return self.refiner.refinement_graph

    def detect_evidence_gap(
        self,
        query: str,
        ctx: RetrievalContext,
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Delegates gap detection to the core application refiner.
        """
        return self.refiner.detect_evidence_gap(
            query=query,
            graph_facts=ctx.graph_facts,
            retrieved_chunks=ctx.retrieved_chunks,
        )

    # --------------------------------------------------------------------------
    # End-to-End Hybrid Execution
    # --------------------------------------------------------------------------
    async def query(
        self,
        query: str,
        session_id: Optional[str] = None,
        use_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes query through 32B Coordinator + Conditional LangGraph Refinement.

        Flow:
            1. Standard 32B Coordinated Retrieval + Conditional Evidence Refinement
               (executed within coordinator.retrieve when enable_evidence_refinement=True).
            2. Unified grounded answer synthesis and AST citation validation.

        Parameters:
            query: Raw user natural language question.
            session_id: Optional session identifier for conversational history.
            use_cache: Whether to use QueryResponseCache. In benchmarks, ALWAYS set
                       to False to ensure complete evaluation isolation.
        """
        t0 = time.time()
        latencies: Dict[str, float] = {}

        # Step 1: Coordinated Retrieval with Conditional Refinement Pass
        t_ret_start = time.time()
        retrieval_ctx = await self.coordinator.retrieve(
            query=query,
            session_id=session_id,
            forced_route=RouteDecision.BOTH,
            enable_evidence_refinement=True,
        )
        latencies["initial_32b_retrieval_ms"] = round((time.time() - t_ret_start) * 1000.0, 2)
        latencies.update(retrieval_ctx.latency_ms)

        refinement_activated = retrieval_ctx.refinement_activated
        missing_ents = retrieval_ctx.missing_entities
        missing_docs = retrieval_ctx.missing_doc_ids

        # Step 2: Assemble Context & Synthesize
        assembled_context, _ = self.synthesizer.assemble_context(retrieval_ctx)
        synth_res = await self.synthesizer.synthesize(retrieval_ctx, use_cache=use_cache)
        latencies["synthesis_ms"] = synth_res.latency_ms.get("total_ms", 10.0)
        total_time_ms = round((time.time() - t0) * 1000.0, 2)
        latencies["total_request_ms"] = total_time_ms

        return {
            "query": query,
            "answer": synth_res.answer,
            "cited_chunk_ids": synth_res.cited_chunk_ids,
            "is_valid": synth_res.validation_result.is_valid,
            "refinement_activated": refinement_activated,
            "missing_entities": missing_ents,
            "missing_doc_ids": missing_docs,
            "retrieval_context": retrieval_ctx,
            "assembled_context": assembled_context,
            "latencies": latencies,
        }
