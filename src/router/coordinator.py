"""
Retrieval Coordinator Module.

Architecture Role:
    Part of Phase 5 (Question Router & Session Memory). Serves as the central query coordinator
    orchestrating session dialogue memory, query intent routing, parameterized Neo4j graph traversals,
    and dense pgvector semantic searches. Packages retrieved heterogeneous context into a unified
    `RetrievalContext` ready for Phase 6 response synthesis and citation validation.

Inputs:
    - Raw user query strings.
    - Optional `session_id` for multi-turn conversational isolation.
    - Retrieval hyperparameters (`top_k` chunk count).

Outputs:
    - Unified `RetrievalContext` containing graph facts, dense vector hits, deduplicated citation IDs,
      and operation latency metrics.
    - Updated `SessionMemory` preserving conversational history within sliding window bounds ($k=3$).

Design Decisions:
    - Decoupled Orchestration: Coordinates separate specialized components (`SessionMemory`,
      `RouteClassifier`, `GraphQueryEngine`, `VectorStore`) without tight coupling.
    - Full Provenance Tracking: Collects and deduplicates `source_chunk_id` foreign keys from both
      graph relationship properties and vector chunk records.
    - Granular Latency Profiling: Records elapsed execution time for routing, graph traversals,
      and vector similarity search individually.
"""

import asyncio
from collections import OrderedDict
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.community import GraphCommunityDetector
from src.graph.query_engine import GraphQueryEngine
from src.graph.templates import QueryTemplateType
from src.memory.session import SessionMemory
from src.router.classifier import RouteClassifier
from src.router.metadata_resolver import MetadataResolver
from src.router.models import RetrievalContext, RouteDecision, RoutingResult
from src.router.refiner import EvidenceRefiner
from src.vector.indexer import DEFAULT_TOP_K, VectorStore
from src.vector.models import VectorSearchResult

logger = setup_logger(name="router.coordinator")

# Multi-hop parameterized Cypher query templates traversing >= 2 relational edges
MULTIHOP_CYPHER_TEMPLATES: Set[QueryTemplateType] = {
    QueryTemplateType.METHOD_ANCESTRY_EXTENDS,
    QueryTemplateType.METHOD_BENCHMARK_COMPARISONS,
    QueryTemplateType.CO_AUTHORSHIP_NETWORK,
    QueryTemplateType.CITATION_CHAIN,
}


def compute_adaptive_hydration_budget(
    num_vector_chunks: int,
    max_vector_score: float,
    num_graph_facts: int,
    unseen_candidate_chunk_ids: List[str],
    target_paper_ids: Set[str],
    vector_doc_ids: Set[str],
    is_multihop_graph: bool,
    max_cap: int = 3,
) -> Tuple[int, str]:
    """
    Computes evidence-gap adaptive hydration budget (Step 32C).

    Given the retrieval state, deterministically returns (budget, reason) where:
    - budget in {0, 1, min(len(unseen), max_cap)}
    - reason in {'no_unseen_graph_chunks', 'direct_vector_sufficient', 'minor_gap', 'multi_hop_gap'}

    Runtime Signals:
    - num_vector_chunks (|V|) and max_vector_score (s_max)
    - num_graph_facts and unseen_candidate_chunk_ids (|U|)
    - target_paper_ids (papers identified from query entities/citations)
    - vector_doc_ids (document IDs retrieved by vector similarity search)
    - is_multihop_graph (explicit existing graph signal: multi-hop template or cross-paper comparison)
    """
    u_count = len(unseen_candidate_chunk_ids)
    if u_count == 0:
        return 0, "no_unseen_graph_chunks"

    # Extract document IDs from unseen graph candidates
    u_doc_ids = {
        cid.replace("chunk_", "").rsplit("_", 1)[0].replace(".", "_")
        for cid in unseen_candidate_chunk_ids
    }

    vector_has_target = bool(target_paper_ids and target_paper_ids.issubset(vector_doc_ids))
    graph_has_target = bool(target_paper_ids and bool(target_paper_ids.intersection(u_doc_ids)))

    # Condition 1: Multi-hop graph traversal linking disconnected literature components
    if is_multihop_graph:
        return min(u_count, max_cap), "multi_hop_gap"

    # Condition 2: Direct vector sufficiency
    # Target paper already present in vector context with confident score (>= 0.72)
    # and graph candidates do not contain the target paper (spurious cross-paper fan-out)
    if vector_has_target and num_vector_chunks >= 2 and max_vector_score >= 0.72:
        if not graph_has_target:
            return 0, "direct_vector_sufficient"
        else:
            return min(u_count, 1), "minor_gap"

    # Direct vector sufficiency for queries without named papers when score is very high
    if num_vector_chunks >= 2 and max_vector_score >= 0.82 and not target_paper_ids:
        return 0, "direct_vector_sufficient"

    # Condition 3: Evidence gap - target paper missing from vector context or weak score
    if target_paper_ids and not vector_has_target:
        return min(u_count, max_cap), "multi_hop_gap"

    if num_vector_chunks < 2 or max_vector_score < 0.72:
        return min(u_count, max_cap), "multi_hop_gap"

    # Condition 4: Minor evidence gap
    return min(u_count, 1), "minor_gap"


class RetrievalCoordinator:
    """
    Coordinates multi-turn conversational memory, intent routing, and multi-modal retrieval.
    """

    def __init__(
        self,
        classifier: Optional[RouteClassifier] = None,
        query_engine: Optional[GraphQueryEngine] = None,
        vector_store: Optional[VectorStore] = None,
        community_detector: Optional[GraphCommunityDetector] = None,
        metadata_resolver: Optional[MetadataResolver] = None,
        enable_graph_passage_hydration: Optional[bool] = None,
        max_graph_hydrated_passages: Optional[int] = None,
        enable_adaptive_hydration: Optional[bool] = None,
        enable_evidence_refinement: Optional[bool] = None,
        max_refined_facts: Optional[int] = None,
        max_refined_chunks: Optional[int] = None,
        refiner: Optional[EvidenceRefiner] = None,
    ) -> None:
        self.query_engine = query_engine or GraphQueryEngine()
        self.classifier = classifier or RouteClassifier(query_engine=self.query_engine)
        self.vector_store = vector_store or VectorStore()
        self.community_detector = community_detector or GraphCommunityDetector(
            writer=getattr(self.query_engine, "writer", None)
        )
        self.metadata_resolver = metadata_resolver or MetadataResolver()
        self.settings = get_settings()

        # Phase 32 Graph-Guided Passage Hydration configuration
        self.enable_graph_passage_hydration = (
            enable_graph_passage_hydration
            if enable_graph_passage_hydration is not None
            else getattr(self.settings, "enable_graph_passage_hydration", False)
        )
        self.max_graph_hydrated_passages = (
            max_graph_hydrated_passages
            if max_graph_hydrated_passages is not None
            else getattr(self.settings, "max_graph_hydrated_passages", 3)
        )
        self.enable_adaptive_hydration = (
            enable_adaptive_hydration
            if enable_adaptive_hydration is not None
            else getattr(self.settings, "enable_adaptive_hydration", False)
        )

        # ADR 070 Bounded LangGraph Evidence Refinement configuration
        self.enable_evidence_refinement = (
            enable_evidence_refinement
            if enable_evidence_refinement is not None
            else getattr(self.settings, "enable_evidence_refinement", False)
        )
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
        self.refiner = refiner

        # Session memory store keyed by session_id
        self._sessions: Dict[str, SessionMemory] = {}

    def _get_refiner(self) -> EvidenceRefiner:
        """
        Lazily initializes the EvidenceRefiner instance if not already provided.
        """
        if self.refiner is None:
            self.refiner = EvidenceRefiner(
                query_engine=self.query_engine,
                vector_store=self.vector_store,
                metadata_resolver=self.metadata_resolver,
                max_refined_facts=self.max_refined_facts,
                max_refined_chunks=self.max_refined_chunks,
            )
        return self.refiner

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionMemory:
        """
        Retrieves existing session memory or initializes a new sliding-window buffer.
        """
        key = session_id or "default_session"
        if key not in self._sessions:
            logger.info("Initializing new SessionMemory buffer for session '%s'", key)
            self._sessions[key] = SessionMemory()
        return self._sessions[key]

    async def warmup(self) -> Dict[str, bool]:
        """
        Pre-warms database connection pools, verifies driver connectivity,
        and initializes vector database tables to eliminate cold-start latencies.
        """
        warmup_status: Dict[str, bool] = {"neo4j": False, "postgres": False}

        # Step 1: Pre-warm Neo4j driver connection pool and sync registry
        try:
            driver = await self.query_engine.writer.get_driver()
            await driver.verify_connectivity()
            if hasattr(self.query_engine, "sync_registry_from_graph"):
                try:
                    await self.query_engine.sync_registry_from_graph()
                except Exception:
                    pass
            warmup_status["neo4j"] = True
            logger.info("Lifespan Warmup: Neo4j connection pool warmed and verified.")
        except Exception as exc:
            logger.warning("Lifespan Warmup: Neo4j warm-up failed: %s", exc)

        # Step 2: Pre-warm PostgreSQL/pgvector engine pool and ensure schema
        try:
            await self.vector_store.initialize()
            async with self.vector_store.engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            warmup_status["postgres"] = True
            logger.info("Lifespan Warmup: PostgreSQL/pgvector connection pool warmed and verified.")
        except Exception as exc:
            logger.warning("Lifespan Warmup: PostgreSQL warm-up failed: %s", exc)

        return warmup_status

    async def _run_graph(self, query: str, entities: Optional[List[str]] = None) -> tuple:
        """
        Executes graph retrieval path, returning (facts, chunk_ids, template_type, latency_ms, error).
        Passes pre-identified entities to avoid redundant registry scans.
        """
        start = time.time()
        try:
            graph_result = await self.query_engine.query(query, pre_identified_entities=entities)
            elapsed = round((time.time() - start) * 1000.0, 2)
            return (
                graph_result.formatted_statements,
                graph_result.source_chunk_ids,
                graph_result.template_type,
                elapsed,
                None,
            )
        except Exception as exc:
            elapsed = round((time.time() - start) * 1000.0, 2)
            logger.error("Graph traversal failed during coordinated retrieval: %s", exc)
            return [], [], None, elapsed, exc

    async def _run_vector(
        self,
        query: str,
        top_k: int,
        entities: Optional[List[str]] = None,
    ) -> tuple:
        """
        Executes vector similarity search path, returning (chunks, latency_ms).
        When entities are detected, looks up their document IDs to eliminate distractor chunks.
        Falls back to unfiltered search if filtered search returns insufficient chunks (< 2).
        """
        start = time.time()
        try:
            filter_doc_ids: Optional[List[str]] = None
            if entities and hasattr(self.vector_store, "get_document_ids_for_entities"):
                lookup = getattr(self.vector_store, "get_document_ids_for_entities")
                import inspect
                if callable(lookup):
                    res = lookup(entities)
                    if inspect.isawaitable(res):
                        filter_doc_ids = await res
                    elif isinstance(res, list):
                        filter_doc_ids = res
                if filter_doc_ids:
                    logger.info("Metadata-isolated vector search enabled for docs: %s", filter_doc_ids)

            chunks = await self.vector_store.similarity_search(
                query, top_k=top_k, filter_document_ids=filter_doc_ids
            )

            # If filtered search returned 0 chunks, fallback to general search
            if filter_doc_ids and len(chunks) == 0:
                logger.info(
                    "Filtered vector search yielded 0 chunks; falling back to general search",
                )
                chunks = await self.vector_store.similarity_search(query, top_k=top_k)

            # Dynamic Top-K & Relevance Threshold Filtering (ADR 033)
            thematic_keywords = {
                "overview", "summary", "summarize", "landscape", "general",
                "compare", "comparison", "comprehensive", "theme", "trends"
            }
            query_lower = query.lower()
            is_thematic = any(w in query_lower for w in thematic_keywords)
            max_k = self.settings.thematic_top_k if is_thematic else min(top_k, self.settings.focused_top_k)

            # Cosine similarity threshold filtering with safety floor
            threshold = self.settings.relevance_score_threshold
            filtered_chunks = [c for c in chunks if c.score >= threshold]
            if not filtered_chunks and chunks:
                # Retain top-1 chunk safety floor to avoid completely wiping context
                filtered_chunks = [chunks[0]]

            chunks = filtered_chunks[:max_k]

            elapsed = round((time.time() - start) * 1000.0, 2)
            return chunks, elapsed, None
        except Exception as exc:
            elapsed = round((time.time() - start) * 1000.0, 2)
            logger.error("Vector similarity search failed during coordinated retrieval: %s", exc)
            return [], elapsed, exc

    async def retrieve(
        self,
        query: str,
        session_id: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
        forced_route: Optional[RouteDecision] = None,
        enable_evidence_refinement: Optional[bool] = None,
    ) -> RetrievalContext:
        """
        Executes end-to-end coordinated retrieval:
        1. Resolves conversational coreference from session memory.
        2. Classifies intent into graph, vector, or both (with low-confidence escalation).
        3. Dispatches retrieval tasks to GraphQueryEngine and/or VectorStore.
           When route is BOTH, graph and vector run in parallel via asyncio.gather.
        4. Aggregates graph facts, vector chunks, and citations.
        5. Updates session memory with the turn context.
        """
        total_start = time.time()
        latencies: Dict[str, float] = {}

        # Step 1: Resolve conversational pronoun coreferences via SessionMemory
        session = self.get_or_create_session(session_id)
        resolved_query = session.resolve_coreference(query)
        logger.info(
            "Query processing: original='%s', resolved='%s' (session='%s')",
            query, resolved_query, session_id or "default",
        )

        # Step 2: Classify retrieval intent with confidence check
        routing_start = time.time()
        routing_result: RoutingResult = await self.classifier.classify(resolved_query)
        latencies["routing_ms"] = round((time.time() - routing_start) * 1000.0, 2)
        if forced_route is not None:
            logger.info("Evaluation route override active: %s -> %s", routing_result.decision.value, forced_route.value)
            routing_result.decision = forced_route

        logger.info(
            "Routing decision: route=%s, confidence=%.2f, reasoning='%s'",
            routing_result.decision.value,
            routing_result.confidence,
            routing_result.reasoning,
        )

        graph_facts: List[str] = []
        retrieved_chunks: List[VectorSearchResult] = []
        cited_chunks_set: Set[str] = set()
        graph_source_cids: List[str] = []
        executed_template_type: Optional[QueryTemplateType] = None

        # Step 3: Dispatch retrieval — parallel when BOTH, sequential otherwise
        if routing_result.decision == RouteDecision.BOTH:
            # Parallel dispatch: graph and vector run concurrently via asyncio.gather
            graph_task = self._run_graph(resolved_query, routing_result.detected_entities)
            vector_task = self._run_vector(resolved_query, top_k, routing_result.detected_entities)
            graph_res, (v_chunks, v_ms, v_err) = await asyncio.gather(
                graph_task, vector_task,
            )
            if len(graph_res) == 5:
                g_facts, g_cids, g_tmpl, g_ms, g_err = graph_res
            else:
                g_facts, g_cids, g_ms, g_err = graph_res
                g_tmpl = None

            executed_template_type = g_tmpl
            graph_facts.extend(g_facts)
            graph_source_cids.extend(g_cids)
            cited_chunks_set.update(g_cids)
            latencies["graph_ms"] = g_ms
            retrieved_chunks.extend(v_chunks)
            for chunk in v_chunks:
                cited_chunks_set.add(chunk.chunk_id)
            latencies["vector_ms"] = v_ms

        elif routing_result.decision == RouteDecision.GRAPH:
            # Sequential graph-first with vector fallback on empty results
            graph_res = await self._run_graph(
                resolved_query, routing_result.detected_entities,
            )
            if len(graph_res) == 5:
                g_facts, g_cids, g_tmpl, g_ms, g_err = graph_res
            else:
                g_facts, g_cids, g_ms, g_err = graph_res
                g_tmpl = None

            executed_template_type = g_tmpl
            latencies["graph_ms"] = g_ms
            if g_err:
                logger.warning("Graph path errored; falling back to vector retrieval")
                routing_result.decision = RouteDecision.BOTH
            else:
                graph_facts.extend(g_facts)
                graph_source_cids.extend(g_cids)
                cited_chunks_set.update(g_cids)
                # Escalate to hybrid if graph yielded 0 facts or 0 chunk citations
                if not graph_facts or not g_cids:
                    logger.info("Graph traversal yielded insufficient chunk citations; escalating to hybrid vector search")
                    routing_result.decision = RouteDecision.BOTH

            # Run vector if escalated
            if routing_result.decision == RouteDecision.BOTH:
                v_chunks, v_ms, v_err = await self._run_vector(resolved_query, top_k, routing_result.detected_entities)
                retrieved_chunks.extend(v_chunks)
                for chunk in v_chunks:
                    cited_chunks_set.add(chunk.chunk_id)
                latencies["vector_ms"] = v_ms

        elif routing_result.decision == RouteDecision.VECTOR:
            v_chunks, v_ms, v_err = await self._run_vector(resolved_query, top_k, routing_result.detected_entities)
            retrieved_chunks.extend(v_chunks)
            for chunk in v_chunks:
                cited_chunks_set.add(chunk.chunk_id)
            latencies["vector_ms"] = v_ms

        # Step 3b: If query seeks high-level corpus themes or summaries, inject community summaries
        is_thematic_query = any(
            phrase in resolved_query.lower()
            for phrase in [
                "overview", "summary", "summarize", "landscape", "themes", "topics",
                "research areas", "corpus", "state of the art", "high level",
            ]
        )
        if is_thematic_query and self.community_detector:
            try:
                summary_context = await self.community_detector.get_corpus_summary_context(
                    resolved_query, max_communities=3
                )
                if summary_context and "No topological communities" not in summary_context:
                    graph_facts.insert(0, summary_context)
            except Exception as exc:
                logger.warning("Failed to retrieve community summary context: %s", exc)

        # Step 3c: Dedicated Document Metadata Resolution (Provenance-Aware Catalog Headers)
        meta_start = time.time()
        try:
            metadata_records = self.metadata_resolver.resolve(
                query=resolved_query,
                detected_entities=routing_result.detected_entities,
            )
            for m_rec in metadata_records:
                cited_chunks_set.add(m_rec.id)
            latencies["metadata_ms"] = round((time.time() - meta_start) * 1000.0, 2)
        except Exception as exc:
            latencies["metadata_ms"] = round((time.time() - meta_start) * 1000.0, 2)
            logger.warning("Metadata resolution failed during retrieval: %s", exc)
            metadata_records = []

        # Step 3d: Evidence Precedence & Conflict Suppression (ADR 052 / Run 3A)
        # Authoritative catalog metadata > Verified graph facts > Normal chunks > Inferred graph statements.
        # Suppress conflicting placeholder author facts ('Unknown Author', 'AUTHOR NAME NOT SPECIFIED')
        # when authoritative document catalog evidence exists.
        suppressed_evidence: List[Dict[str, Any]] = []
        if metadata_records and graph_facts:
            placeholder_author_re = re.compile(
                r"\b(unknown\s+author|author\s+name\s+not\s+specified|not\s+specified|anonymous)\b",
                re.IGNORECASE,
            )
            chunk_id_re = re.compile(r"\[chunk:\s*([a-zA-Z0-9_\.]+)\]")

            retained_facts: List[str] = []
            for fact in graph_facts:
                fact_lower = fact.lower()
                is_author_statement = "author" in fact_lower or "[:authored_by]" in fact_lower
                has_placeholder = bool(placeholder_author_re.search(fact))

                if is_author_statement and has_placeholder:
                    suppressed = False
                    c_match = chunk_id_re.search(fact)
                    src_id = c_match.group(1) if c_match else "unknown_chunk"
                    for m_rec in metadata_records:
                        paper_title_lower = m_rec.title.lower()
                        clean_pid = m_rec.paper_id.replace(".", "_")
                        if (
                            paper_title_lower in fact_lower
                            or m_rec.title.split(":")[0].strip().lower() in fact_lower
                            or clean_pid in src_id
                            or clean_pid in fact_lower
                        ):
                            suppression_record = {
                                "suppressed_evidence": True,
                                "reason": "placeholder_conflict",
                                "source_id": src_id,
                                "authoritative_source_id": m_rec.id,
                                "suppressed_fact": fact,
                            }
                            suppressed_evidence.append(suppression_record)
                            logger.info(
                                "ADR 052 Evidence Precedence: Suppressed placeholder fact '%s' in favor of authoritative catalog '%s'",
                                fact,
                                m_rec.id,
                            )
                            suppressed = True
                            break
                    if not suppressed:
                        retained_facts.append(fact)
                else:
                    retained_facts.append(fact)

            graph_facts = retained_facts

        # Step 3e: Phase 32 Graph-Guided Passage Hydration (Step 32A / Step 32C Adaptive)
        candidate_graph_cids: List[str] = []
        selected_graph_cids: List[str] = []
        hydrated_cids: List[str] = []
        dropped_budget_cids: List[str] = []
        hydration_budget: int = 0
        hydration_reason: str = "disabled"

        if self.enable_graph_passage_hydration and graph_source_cids:
            hydration_start = time.time()
            # 1. Collect unique source_chunk_ids preserving graph traversal discovery order
            candidate_graph_cids = list(dict.fromkeys(graph_source_cids))

            # Exclude chunks from suppressed placeholder evidence (ADR 052)
            suppressed_cids = {s.get("source_id") for s in suppressed_evidence if s.get("source_id")}
            candidate_graph_cids = [cid for cid in candidate_graph_cids if cid not in suppressed_cids]

            # 2. Remove chunks already in vector results
            existing_v_ids = {c.chunk_id for c in retrieved_chunks}
            remaining_cids = [cid for cid in candidate_graph_cids if cid not in existing_v_ids]

            # 3. Deterministically rank remaining IDs by graph-path relevance:
            # Frequency across graph traversal paths (descending), tie-broken by first-seen traversal order (ascending)
            remaining_cids.sort(
                key=lambda cid: (-graph_source_cids.count(cid), graph_source_cids.index(cid))
            )

            # Step 32C: Evidence-Gap Adaptive Budgeting
            if self.enable_adaptive_hydration:
                # Document IDs from vector hits and unseen graph candidates
                v_doc_ids = {
                    c.chunk_id.replace("chunk_", "").rsplit("_", 1)[0].replace(".", "_")
                    for c in retrieved_chunks
                }
                u_doc_ids = {
                    cid.replace("chunk_", "").rsplit("_", 1)[0].replace(".", "_")
                    for cid in remaining_cids
                }

                # Deterministic identification of query-targeted papers via metadata resolver catalog
                target_pids: Set[str] = set()
                if self.metadata_resolver and hasattr(self.metadata_resolver, "_indexed_papers"):
                    q_lower = resolved_query.lower()
                    for p_meta in self.metadata_resolver._indexed_papers:
                        pid = p_meta.get("paper_id", "") if isinstance(p_meta, dict) else getattr(p_meta, "paper_id", "")
                        pid_clean = pid.replace(".", "_")
                        title_clean = (p_meta.get("title", "") if isinstance(p_meta, dict) else getattr(p_meta, "title", "")).lower()
                        short_title = title_clean.split(":")[0].strip()
                        if (
                            (pid_clean and pid_clean.lower() in q_lower)
                            or (title_clean and title_clean in q_lower)
                            or (len(short_title) > 10 and short_title in q_lower)
                        ):
                            target_pids.add(pid_clean)

                # Deterministic definition of "disconnected literature components":
                # 1. Multi-hop Cypher template executed (METHOD_ANCESTRY_EXTENDS, METHOD_BENCHMARK_COMPARISONS, CO_AUTHORSHIP_NETWORK, CITATION_CHAIN)
                # 2. Graph candidates bridge multiple distinct document components (len(u_doc_ids) >= 2)
                # 3. Traversal connects to document components completely absent from vector hits (u_doc_ids - v_doc_ids)
                #    in the presence of comparative query intent
                # 4. Query targets >= 2 distinct papers
                is_comparative = any(
                    w in resolved_query.lower()
                    for w in [
                        "compare", "comparison", "versus", "vs", "difference",
                        "trade-off", "tradeoff", "better", "relative to", "shared", "evolution",
                    ]
                )
                has_disconnected_docs = (len(u_doc_ids) >= 2) or bool(u_doc_ids - v_doc_ids)
                is_multihop_graph = bool(
                    (executed_template_type in MULTIHOP_CYPHER_TEMPLATES)
                    or (is_comparative and has_disconnected_docs)
                    or (len(target_pids) >= 2)
                )

                hydration_budget, hydration_reason = compute_adaptive_hydration_budget(
                    num_vector_chunks=len(retrieved_chunks),
                    max_vector_score=max((c.score for c in retrieved_chunks), default=0.0),
                    num_graph_facts=len(graph_facts),
                    unseen_candidate_chunk_ids=remaining_cids,
                    target_paper_ids=target_pids,
                    vector_doc_ids=v_doc_ids,
                    is_multihop_graph=is_multihop_graph,
                    max_cap=self.max_graph_hydrated_passages,
                )
            else:
                hydration_budget = min(len(remaining_cids), self.max_graph_hydrated_passages)
                hydration_reason = "static_budget" if remaining_cids else "no_unseen_graph_chunks"

            # 4. Deterministically select top <= hydration_budget
            selected_graph_cids = remaining_cids[: hydration_budget]
            dropped_budget_cids = remaining_cids[hydration_budget :]

            # Logging requirement (Safeguard 2)
            logger.info(
                "Step 32C Adaptive Hydration Decision: |V|=%d, s_max=%.4f, |G|=%d, |U|=%d -> budget=%d, reason='%s', selected_cids=%s",
                len(retrieved_chunks),
                max((c.score for c in retrieved_chunks), default=0.0),
                len(graph_facts),
                len(remaining_cids),
                hydration_budget,
                hydration_reason,
                selected_graph_cids,
            )

            # 5. Hydrate full chunk text from PostgreSQL/pgvector primary key index
            if selected_graph_cids:
                try:
                    hydrated_chunks = await self.vector_store.get_chunks_by_ids(selected_graph_cids)
                    for h_chunk in hydrated_chunks:
                        retrieved_chunks.append(h_chunk)
                        cited_chunks_set.add(h_chunk.chunk_id)
                        hydrated_cids.append(h_chunk.chunk_id)
                except Exception as exc:
                    logger.error("Phase 32 Graph passage hydration failed: %s", exc)

            latencies["graph_hydration_ms"] = round((time.time() - hydration_start) * 1000.0, 2)
        elif self.enable_graph_passage_hydration:
            hydration_budget = 0
            hydration_reason = "no_graph_candidates"

        # Step 3f: Conditional Bounded LangGraph Evidence Refinement (ADR 070)
        should_refine = (
            enable_evidence_refinement
            if enable_evidence_refinement is not None
            else self.enable_evidence_refinement
        )
        refinement_activated = False
        missing_entities_list: List[str] = []
        missing_doc_ids_list: List[str] = []
        refined_facts_count = 0
        refined_chunks_count = 0

        if should_refine:
            refine_start = time.time()
            try:
                refiner_instance = self._get_refiner()
                refine_result = await refiner_instance.refine(
                    query=resolved_query,
                    initial_graph_facts=graph_facts,
                    initial_chunks=retrieved_chunks,
                )
                if refine_result.get("refinement_activated"):
                    refinement_activated = True
                    missing_entities_list = refine_result.get("missing_entities", [])
                    missing_doc_ids_list = refine_result.get("missing_doc_ids", [])
                    extra_facts = refine_result.get("refined_graph_facts", [])
                    extra_chunks = refine_result.get("refined_chunks", [])

                    # Provenance Invariant: Extract source chunk IDs from graph statements
                    # and append chunk IDs from refined vector chunks. Every claim must
                    # resolve to an authentic, validated chunk ID.
                    if extra_facts:
                        graph_facts.extend(extra_facts)
                        refined_facts_count = len(extra_facts)
                        for f in extra_facts:
                            cids = re.findall(r"\[chunk\s*:\s*([^\]]+)\]", f, flags=re.I)
                            cited_chunks_set.update(cids)

                    if extra_chunks:
                        retrieved_chunks.extend(extra_chunks)
                        refined_chunks_count = len(extra_chunks)
                        for c in extra_chunks:
                            cited_chunks_set.add(c.chunk_id)

                latencies["langgraph_refinement_total_ms"] = round((time.time() - refine_start) * 1000.0, 2)
                latencies.update(refine_result.get("latencies", {}))
            except Exception as exc:
                latencies["langgraph_refinement_total_ms"] = round((time.time() - refine_start) * 1000.0, 2)
                logger.warning("Evidence refinement failed; falling back to unrefined context: %s", exc)

        # Step 4: Update session memory with entities extracted in this turn
        session.add_user_turn(
            text=resolved_query,
            entities=routing_result.detected_entities,
        )

        # Step 5: Extract traversed subgraph for inline response visualization
        subgraph: Optional[Dict[str, Any]] = None
        if graph_facts or routing_result.detected_entities:
            try:
                subgraph = await self.query_engine.get_query_subgraph(routing_result.detected_entities, limit=30)
            except Exception as exc:
                logger.warning("Failed to extract query subgraph: %s", exc)

        latencies["total_ms"] = round((time.time() - total_start) * 1000.0, 2)

        # Step 6: Construct and return unified RetrievalContext
        return RetrievalContext(
            query=resolved_query,
            route=routing_result.decision,
            graph_facts=graph_facts,
            retrieved_chunks=retrieved_chunks,
            cited_chunk_ids=sorted(list(cited_chunks_set)),
            latency_ms=latencies,
            subgraph=subgraph,
            metadata_records=metadata_records,
            suppressed_evidence=suppressed_evidence,
            candidate_graph_chunk_ids=candidate_graph_cids,
            selected_graph_chunk_ids=selected_graph_cids,
            hydrated_chunk_ids=hydrated_cids,
            dropped_due_to_budget=dropped_budget_cids,
            hydration_budget=hydration_budget,
            hydration_reason=hydration_reason,
            refinement_activated=refinement_activated,
            refined_facts_count=refined_facts_count,
            refined_chunks_count=refined_chunks_count,
            missing_entities=missing_entities_list,
            missing_doc_ids=missing_doc_ids_list,
        )

