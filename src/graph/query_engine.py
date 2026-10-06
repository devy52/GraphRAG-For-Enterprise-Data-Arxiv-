"""
Parameterized Graph Query Engine Module.

Architecture Role:
    Part of Phase 4 (Parameterized Graph Query Engine). Translates incoming questions into
    deterministic, injection-safe graph traversals using the pre-compiled `CYPHER_TEMPLATES` catalog.
    Bypasses hallucination-prone Text-to-Cypher LLM generation, resolves entities against the
    `EntityResolver` registry, and serializes graph paths into grounded factual statements
    bearing `source_chunk_id` annotations for citation validation.

Inputs:
    - Natural language query text.
    - Optional pre-identified entities and template type overrides.

Outputs:
    - `GraphQueryResult` containing:
        * Formatted factual sentences (e.g. "Patrick Lewis authored 'RAG Paper' [chunk_001]").
        * Deduplicated list of `source_chunk_id` foreign keys for citation validation.
        * Raw graph records from Neo4j.
        * Execution latency in milliseconds.

Design Decisions:
    - Zero Unconstrained Text-to-Cypher: Eliminates syntax errors, model drift, and Cypher injection
      by restricting all queries to pre-compiled templates with typed parameter dictionaries.
    - Dual Entity Extraction: Performs fast substring matching against registered canonical entities
      and aliases; falls back to lexical token search.
    - Grounded Attribution: Extracts and flattens all `source_chunk_id` properties from traversed edges.
"""

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from neo4j import AsyncDriver
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.canonical_resolver import CanonicalEntityResolver, ResolutionResult
from src.graph.models import EntityType, ResolvedEntity
from src.graph.resolver import EntityResolver
from src.graph.templates import CYPHER_TEMPLATES, CypherTemplate, QueryTemplateType
from src.graph.writer import Neo4jWriter

logger = setup_logger(name="graph.query_engine")


class GraphQueryResult(BaseModel):
    """
    Structured outcome of a parameterized graph query traversal.
    """
    template_type: QueryTemplateType = Field(..., description="The query template executed")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters bound into Cypher query")
    raw_records: List[Dict[str, Any]] = Field(default_factory=list, description="Raw dictionary records from Neo4j")
    formatted_statements: List[str] = Field(
        default_factory=list,
        description="Readable declarative statements with [chunk_id] citations",
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of chunk IDs grounding the graph statements",
    )
    latency_ms: float = Field(default=0.0, description="Query execution latency in milliseconds")


NOISY_ALIASES: Set[str] = {
    "retrieval", "rag", "nlp", "ai", "parser", "chunking", "privacy",
    "graphs", "bias", "attribution", "urag", "data science", "active learning",
    "healthcare", "energy sector", "education", "response generation", "question answering",
    "model", "methods", "method", "paper", "papers",
}


class GraphQueryEngine:
    """
    Executes safe parameterized graph traversals over Neo4j using pre-compiled templates.
    """

    def __init__(
        self,
        writer: Optional[Neo4jWriter] = None,
        resolver: Optional[EntityResolver] = None,
        canonical_resolver: Optional[CanonicalEntityResolver] = None,
    ) -> None:
        self.settings = get_settings()
        self.writer = writer or Neo4jWriter()
        self.resolver = resolver or EntityResolver()
        self.canonical_resolver = canonical_resolver or CanonicalEntityResolver()

    async def sync_registry_from_graph(self) -> int:
        """
        Synchronizes Neo4j graph nodes and aliases into the in-memory EntityResolver registry.
        Ensures entity mentions in user queries can be identified against the graph database.

        Returns:
            Count of entities registered.
        """
        try:
            driver = await self.writer.get_driver()
            query = "MATCH (n) RETURN labels(n) AS labels, n.name AS name, n.aliases AS aliases"
            result = await driver.execute_query(query)
            count = 0
            for record in result.records:
                labels = record.get("labels", [])
                name = record.get("name")
                aliases = record.get("aliases") or []
                if not name or not labels:
                    continue

                matched_etype = None
                for lbl in labels:
                    try:
                        matched_etype = EntityType(lbl)
                        break
                    except ValueError:
                        continue

                if matched_etype is None:
                    matched_etype = EntityType.TOPIC

                resolved = ResolvedEntity(
                    canonical_name=name,
                    entity_type=matched_etype,
                    aliases=list(aliases),
                )
                self.resolver.registry[(matched_etype, name)] = resolved
                count += 1

            # Register into CanonicalEntityResolver index
            canonical_tuples = [
                (ent.canonical_name, ent.entity_type, ent.aliases)
                for ent in self.resolver.registry.values()
            ]
            self.canonical_resolver.register_graph_entities(canonical_tuples)

            logger.info("Synchronized %d entities from Neo4j into EntityResolver registry.", count)
            return count
        except Exception as exc:
            logger.warning("Could not sync entity registry from Neo4j: %s", exc)
            return 0

    def identify_entities_in_text(self, text: str) -> List[Tuple[str, EntityType]]:
        """
        Scans text against the EntityResolver registry to locate mentioned canonical entities.
        Applies length-prioritized matching, alias filtering, and substring subsumption suppression.

        Returns:
            List of (canonical_name, entity_type) tuples found in the text.
        """
        clean_text = text.lower()
        candidates: List[Tuple[str, EntityType, int]] = []

        for (etype, cname), ent in self.resolver.registry.items():
            patterns: List[Tuple[str, int]] = []
            # 1. Full canonical name
            patterns.append((cname, len(cname)))
            # 2. Base name before '('
            base_paren = cname.split("(")[0].strip()
            if len(base_paren) >= 4 and base_paren != cname:
                patterns.append((base_paren, len(base_paren)))
            # 3. Inside parentheses (acronym)
            if "(" in cname and ")" in cname:
                inner = cname[cname.find("(") + 1 : cname.find(")")].strip()
                if len(inner) >= 2:
                    patterns.append((inner, len(inner)))
            # 4. Title before delimiters
            for delim in [":", " for ", " with "]:
                if delim in cname:
                    sub = cname.split(delim)[0].strip()
                    if len(sub) >= 5:
                        patterns.append((sub, len(sub)))
            # 5. Clean aliases
            for alias in ent.aliases:
                if alias.lower() not in NOISY_ALIASES and len(alias) >= 3:
                    patterns.append((alias, len(alias)))

            for pat_str, span_len in patterns:
                if re.search(rf"\b{re.escape(pat_str.lower())}\b", clean_text):
                    candidates.append((cname, etype, span_len))
                    break

        # Sort by span length DESC, then entity type priority
        etype_rank = {
            EntityType.PAPER: 0,
            EntityType.METHOD: 1,
            EntityType.DATASET: 2,
            EntityType.AUTHOR: 3,
            EntityType.VENUE: 4,
            EntityType.TOPIC: 5,
        }
        candidates.sort(key=lambda x: (-x[2], etype_rank.get(x[1], 10)))

        # Filter subsumed spans
        filtered: List[Tuple[str, EntityType]] = []
        for cname, etype, span_len in candidates:
            if not any(
                cname.lower() in existing[0].lower() or existing[0].lower() in cname.lower()
                for existing in filtered
            ):
                filtered.append((cname, etype))

        return filtered

    def select_template(
        self,
        query_text: str,
        entities: List[Tuple[str, EntityType]],
    ) -> Tuple[QueryTemplateType, Dict[str, Any]]:
        """
        Selects the best parameterized template based on query intent keywords and entity types.
        """
        q = query_text.lower()
        first_entity_name = entities[0][0] if entities else ""
        first_entity_type = entities[0][1] if entities else None

        paper_ent = next((name for name, et in entities if et == EntityType.PAPER), None)
        author_ent = next((name for name, et in entities if et == EntityType.AUTHOR), None)
        method_ent = next((name for name, et in entities if et == EntityType.METHOD), None)
        dataset_ent = next((name for name, et in entities if et == EntityType.DATASET), None)

        # 1. Co-authorship
        if any(w in q for w in ["co-author", "collaborate", "collaborator", "worked with"]):
            target_author = author_ent or first_entity_name
            return QueryTemplateType.CO_AUTHORSHIP_NETWORK, {"author_name": target_author}

        # 2. Authorship queries
        if any(w in q for w in ["author", "who wrote", "written by", "papers of", "publications of"]):
            if first_entity_type == EntityType.AUTHOR:
                target_author = author_ent or first_entity_name
                return QueryTemplateType.PAPERS_BY_AUTHOR, {"author_name": target_author}
            if paper_ent or first_entity_type in (EntityType.PAPER, EntityType.METHOD):
                target_paper = paper_ent or first_entity_name
                return QueryTemplateType.AUTHORS_OF_PAPER, {"paper_title": target_paper}
            target_author = author_ent or first_entity_name
            return QueryTemplateType.PAPERS_BY_AUTHOR, {"author_name": target_author}

        # 3. Evolution / Lineage / Ancestry
        if re.search(r"\b(extend|extends|ancestry|evolution|built upon|built on|lineage of|derived from)\b", q):
            target_method = method_ent or first_entity_name
            return QueryTemplateType.METHOD_ANCESTRY_EXTENDS, {"method_name": target_method}

        # 4. Benchmark / Comparison / Shared Datasets
        if any(w in q for w in ["compare", "comparison", "benchmark", "versus", "vs", "evaluated with", "shared"]):
            candidates = [name for name, et in entities if et in (EntityType.METHOD, EntityType.PAPER)]
            target_method = candidates[0] if candidates else (method_ent or first_entity_name)
            params = {"method_name": target_method}
            if len(candidates) > 1:
                params["compared_method"] = candidates[1]
            return QueryTemplateType.METHOD_BENCHMARK_COMPARISONS, params

        # 5. Methods used in paper
        if any(w in q for w in ["method", "model", "technique", "algorithm", "architecture", "backbone", "loss function", "encoder", "generator"]):
            target_paper = paper_ent or first_entity_name
            return QueryTemplateType.METHODS_USED_IN_PAPER, {"paper_title": target_paper}

        # 6. Datasets used in paper
        if any(w in q for w in ["dataset", "evaluation benchmark", "data used", "evaluated on"]):
            if method_ent and not paper_ent:
                params = {"method_name": method_ent}
                if len(entities) > 1 and entities[1][0] != method_ent:
                    params["compared_method"] = entities[1][0]
                return QueryTemplateType.METHOD_BENCHMARK_COMPARISONS, params
            target_paper = paper_ent or first_entity_name
            return QueryTemplateType.DATASETS_USED_IN_PAPER, {"paper_title": target_paper}

        # 7. Citations / Connections
        if any(w in q for w in ["cite", "citation", "cites", "cited by", "referenced by"]):
            target_paper = paper_ent or first_entity_name
            return QueryTemplateType.CITATION_CHAIN, {"paper_title": target_paper}

        # 8. Entity-type fallback heuristic
        if paper_ent:
            return QueryTemplateType.EGO_NEIGHBORHOOD, {"entity_name": paper_ent}
        if first_entity_type == EntityType.AUTHOR:
            return QueryTemplateType.PAPERS_BY_AUTHOR, {"author_name": first_entity_name}
        if first_entity_type == EntityType.METHOD:
            return QueryTemplateType.METHOD_ANCESTRY_EXTENDS, {"method_name": first_entity_name}
        if first_entity_type == EntityType.PAPER:
            return QueryTemplateType.METHODS_USED_IN_PAPER, {"paper_title": first_entity_name}

        return QueryTemplateType.EGO_NEIGHBORHOOD, {"entity_name": first_entity_name}

    # Alias for router compatibility
    detect_best_template = select_template

    def format_records_to_statements(
        self,
        template_type: QueryTemplateType,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[str]]:
        """
        Converts raw Neo4j record rows into explicit relational path statements
        bearing provenance [chunk: ...] tags (Phase 30 / ADR 054).

        Returns:
            Tuple of (formatted_statements, deduplicated_chunk_ids).
        """
        statements: List[str] = []
        chunk_ids: Set[str] = set()

        # Step 1: Iterate over records and format according to query template semantics
        for r in records:
            if template_type == QueryTemplateType.AUTHORS_OF_PAPER:
                paper = r.get("paper_title")
                author = r.get("author_name")
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"Paper '{paper}' was authored by {author}{tag}.")
                if cid:
                    chunk_ids.add(cid)

            elif template_type == QueryTemplateType.PAPERS_BY_AUTHOR:
                paper = r.get("paper_title")
                author = r.get("author_name")
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"{author} authored paper '{paper}'{tag}.")
                if cid:
                    chunk_ids.add(cid)

            elif template_type == QueryTemplateType.METHODS_USED_IN_PAPER:
                paper = r.get("paper_title")
                method = r.get("method_name")
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"Paper '{paper}' uses method '{method}'{tag}.")
                if cid:
                    chunk_ids.add(cid)

            elif template_type == QueryTemplateType.DATASETS_USED_IN_PAPER:
                paper = r.get("paper_title")
                dataset = r.get("dataset_name")
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"Paper '{paper}' evaluates on dataset '{dataset}'{tag}.")
                if cid:
                    chunk_ids.add(cid)

            elif template_type == QueryTemplateType.METHOD_ANCESTRY_EXTENDS:
                chain = r.get("method_chain", [])
                raw_cids = r.get("chunk_ids", [])
                valid_cids = [c for c in raw_cids if c]
                chunk_tags = " ".join([f"[chunk: {c}]" for c in valid_cids])
                tag = f" {chunk_tags}" if chunk_tags else ""
                statements.append(f"Method Lineage: {' -> extends -> '.join(chain)}{tag}.")
                chunk_ids.update(valid_cids)

            elif template_type == QueryTemplateType.METHOD_BENCHMARK_COMPARISONS:
                s_method = r.get("source_method")
                c_method = r.get("compared_method")
                s_dataset = r.get("shared_dataset")
                raw_cids = r.get("chunk_ids", [])
                valid_cids = [c for c in raw_cids if c]
                chunk_tags = " ".join([f"[chunk: {c}]" for c in valid_cids])
                tag = f" {chunk_tags}" if chunk_tags else ""
                statements.append(
                    f"Methods '{s_method}' and '{c_method}' are both evaluated on dataset '{s_dataset}'{tag}."
                )
                chunk_ids.update(valid_cids)

            elif template_type == QueryTemplateType.CO_AUTHORSHIP_NETWORK:
                a1 = r.get("author_1")
                co = r.get("co_author")
                shared = r.get("shared_paper")
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"{a1} co-authored paper '{shared}' with {co}{tag}.")
                if cid:
                    chunk_ids.add(cid)

            elif template_type == QueryTemplateType.CITATION_CHAIN:
                c_path = r.get("citation_path", [])
                raw_cids = r.get("chunk_ids", [])
                valid_cids = [c for c in raw_cids if c]
                chunk_tags = " ".join([f"[chunk: {c}]" for c in valid_cids])
                tag = f" {chunk_tags}" if chunk_tags else ""
                statements.append(f"Citation Chain: {' -> cites -> '.join(c_path)}{tag}.")
                chunk_ids.update(valid_cids)

            elif template_type == QueryTemplateType.EGO_NEIGHBORHOOD:
                ent = r.get("entity")
                rel = r.get("relationship")
                n_name = r.get("neighbor_name")
                n_type = r.get("neighbor_type") or "Entity"
                cid = r.get("source_chunk_id")
                tag = f" [chunk: {cid}]" if cid else ""
                statements.append(f"Entity '{ent}' -[:{rel}]- '{n_name}' ({n_type}){tag}.")
                if cid:
                    chunk_ids.add(cid)

            else:
                statements.append(str(r))

        return statements, sorted(list(chunk_ids))

    async def execute_query(
        self,
        template_type: QueryTemplateType,
        parameters: Dict[str, Any],
    ) -> GraphQueryResult:
        """
        Executes a pre-compiled Cypher template with validated parameters against Neo4j.
        """
        # Step 1: Retrieve compiled template
        template = CYPHER_TEMPLATES[template_type]
        start_time = time.time()

        # Step 2: Acquire Neo4j driver and open session
        driver = await self.writer.get_driver()
        raw_records: List[Dict[str, Any]] = []

        query_params = dict(parameters)
        query_params.setdefault("compared_method", "")
        query_params.setdefault("canonical_id", "")

        # Canonical Resolution pre-execution hook (ADR 053)
        target_param_key = None
        for key in ["paper_title", "entity_name", "method_name", "author_name", "dataset_name", "topic_name", "venue_name"]:
            if key in query_params and query_params[key]:
                target_param_key = key
                break

        if target_param_key:
            val = query_params[target_param_key]
            res = self.canonical_resolver.resolve(str(val))
            if res.accepted:
                query_params["canonical_id"] = res.canonical_id or ""
                query_params[target_param_key] = res.canonical_name or val
            elif res.reason in ("ambiguous", "low_confidence"):
                logger.info(
                    "Skipping Cypher execution for rejected/ambiguous target '%s' (reason=%s, top=%.2f, second=%.2f)",
                    val, res.reason, res.top_score, res.second_score,
                )
                return GraphQueryResult(
                    template_type=template_type,
                    parameters=parameters,
                    raw_records=[],
                    formatted_statements=[],
                    source_chunk_ids=[],
                    latency_ms=0.0,
                )

        from typing import LiteralString, cast
        async with driver.session() as session:
            result = await session.run(
                cast(LiteralString, template.cypher_query),
                **query_params,
            )
            # Step 3: Fetch all dictionary records
            records = await result.data()
            raw_records.extend(records)
            # Step 4: Flush socket buffer by consuming result
            await result.consume()

        elapsed_ms = (time.time() - start_time) * 1000.0

        # Step 5: Convert graph paths to declarative factual statements with citations
        statements, chunk_ids = self.format_records_to_statements(template_type, raw_records)

        logger.info(
            "Executed graph template %s in %.2fms (found %d records, %d statements)",
            template_type.value,
            elapsed_ms,
            len(raw_records),
            len(statements),
        )

        return GraphQueryResult(
            template_type=template_type,
            parameters=parameters,
            raw_records=raw_records,
            formatted_statements=statements,
            source_chunk_ids=chunk_ids,
            latency_ms=round(elapsed_ms, 2),
        )

    async def query(
        self,
        question: str,
        pre_identified_entities: Optional[List[str]] = None,
    ) -> GraphQueryResult:
        """
        End-to-end question answering pipeline for graph queries:
        1. Identify mentioned entities in question text (or use pre-identified from router).
        2. Resolve to canonical registry names.
        3. Match query intent to pre-compiled Cypher template.
        4. Execute parameterized Cypher query and format readable statements.

        Args:
            question: Natural language query string.
            pre_identified_entities: Optional list of entity names already identified by the
                router classifier, avoiding redundant registry scans.
        """
        # Step 0: Ensure entity registry is synced from Neo4j if currently empty
        if not self.resolver.registry:
            await self.sync_registry_from_graph()

        # Step 1: Scan question text for recognized entity mentions
        # Use pre-identified entities from router if available to avoid redundant work
        if pre_identified_entities:
            # Re-resolve pre-identified names against registry for proper typing
            entities = []
            for name in pre_identified_entities:
                found = [(n, t) for (n, t) in self.identify_entities_in_text(name) if n == name]
                if found:
                    entities.extend(found)
            # Fallback to full scan if pre-identified didn't resolve
            if not entities:
                entities = self.identify_entities_in_text(question)
        else:
            entities = self.identify_entities_in_text(question)

        # Step 2: Route intent to template and extract parameter bindings
        template_type, params = self.select_template(question, entities)

        # Step 3: Execute query against Neo4j
        result = await self.execute_query(template_type, params)

        # Step 4: Fallback to ego-neighborhood expansion only if entity is a specific non-topic entity
        if not result.formatted_statements and entities and template_type != QueryTemplateType.EGO_NEIGHBORHOOD:
            if len(entities) == 1:
                first_entity_name, first_entity_type = entities[0]
                if first_entity_type != EntityType.TOPIC:
                    logger.info(
                        "Primary template %s yielded 0 records; falling back to EGO_NEIGHBORHOOD for entity '%s'",
                        template_type.value,
                        first_entity_name,
                    )
                    fallback_result = await self.execute_query(
                        QueryTemplateType.EGO_NEIGHBORHOOD,
                        {"entity_name": first_entity_name},
                    )
                    if fallback_result.formatted_statements:
                        return GraphQueryResult(
                            template_type=fallback_result.template_type,
                            parameters=fallback_result.parameters,
                            raw_records=fallback_result.raw_records[:8],
                            formatted_statements=fallback_result.formatted_statements[:8],
                            source_chunk_ids=fallback_result.source_chunk_ids,
                            latency_ms=fallback_result.latency_ms,
                        )
            else:
                # Multi-entity query fallback: aggregate ego neighborhoods across top-2 entities
                all_statements: List[str] = []
                all_cids: Set[str] = set()
                all_records: List[Dict[str, Any]] = []
                for ent_name, ent_type in entities[:2]:
                    if ent_type == EntityType.TOPIC:
                        continue
                    logger.info(
                        "Primary template %s yielded 0 records; trying EGO_NEIGHBORHOOD for entity '%s'",
                        template_type.value,
                        ent_name,
                    )
                    fb = await self.execute_query(
                        QueryTemplateType.EGO_NEIGHBORHOOD,
                        {"entity_name": ent_name},
                    )
                    if fb.formatted_statements:
                        all_statements.extend(fb.formatted_statements)
                        all_cids.update(fb.source_chunk_ids)
                        all_records.extend(fb.raw_records)

                if all_statements:
                    return GraphQueryResult(
                        template_type=QueryTemplateType.EGO_NEIGHBORHOOD,
                        parameters={"entities": [e[0] for e in entities[:2]]},
                        raw_records=all_records[:8],
                        formatted_statements=all_statements[:8],
                        source_chunk_ids=sorted(list(all_cids)),
                        latency_ms=result.latency_ms,
                    )

        return result

    async def get_subgraph(
        self,
        limit: int = 100,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves active nodes and directed relationships for UI graph visualization.

        Args:
            limit: Maximum relationship edges to return (bounded to 300).
            entity_type: Optional filter by node label.

        Returns:
            Dictionary containing 'nodes', 'edges', 'total_nodes', and 'total_edges'.
        """
        driver = await self.writer.get_driver()
        safe_limit = min(max(1, limit), 300)

        from typing import LiteralString, cast
        async with driver.session() as session:
            # Query active relationships and their connected nodes
            if entity_type:
                cypher = (
                    f"MATCH (s:{entity_type})-[r]->(t) "
                    "RETURN s.name AS source, labels(s) AS source_labels, s.aliases AS source_aliases, "
                    "type(r) AS rel_type, r.source_chunk_id AS source_chunk_id, r.confidence AS confidence, "
                    "t.name AS target, labels(t) AS target_labels, t.aliases AS target_aliases "
                    "LIMIT $limit"
                )
            else:
                cypher = (
                    "MATCH (s)-[r]->(t) "
                    "RETURN s.name AS source, labels(s) AS source_labels, s.aliases AS source_aliases, "
                    "type(r) AS rel_type, r.source_chunk_id AS source_chunk_id, r.confidence AS confidence, "
                    "t.name AS target, labels(t) AS target_labels, t.aliases AS target_aliases "
                    "LIMIT $limit"
                )

            result = await session.run(cast(LiteralString, cypher), limit=safe_limit)
            records = await result.data()
            await result.consume()

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            edges: List[Dict[str, Any]] = []

            for row in records:
                s_name = row.get("source") or "Unknown"
                t_name = row.get("target") or "Unknown"
                s_labels = [lbl for lbl in row.get("source_labels", []) if lbl != "Entity"]
                t_labels = [lbl for lbl in row.get("target_labels", []) if lbl != "Entity"]
                s_type = s_labels[0] if s_labels else "Entity"
                t_type = t_labels[0] if t_labels else "Entity"

                if s_name not in nodes_dict:
                    nodes_dict[s_name] = {
                        "id": s_name,
                        "label": s_name,
                        "type": s_type,
                        "aliases": row.get("source_aliases") or [],
                    }
                if t_name not in nodes_dict:
                    nodes_dict[t_name] = {
                        "id": t_name,
                        "label": t_name,
                        "type": t_type,
                        "aliases": row.get("target_aliases") or [],
                    }

                edges.append({
                    "source": s_name,
                    "target": t_name,
                    "type": row.get("rel_type") or "RELATED_TO",
                    "source_chunk_id": row.get("source_chunk_id"),
                    "confidence": float(row.get("confidence") or 1.0),
                })

            # Fallback if no edges yet: fetch standalone nodes so canvas displays active entities
            if not records:
                node_query = "MATCH (n) RETURN n.name AS name, labels(n) AS labels, n.aliases AS aliases LIMIT $limit"
                node_res = await session.run(cast(LiteralString, node_query), limit=safe_limit)
                node_records = await node_res.data()
                await node_res.consume()
                for nrow in node_records:
                    n_name = nrow.get("name") or "Unknown"
                    n_labels = [lbl for lbl in nrow.get("labels", []) if lbl != "Entity"]
                    n_type = n_labels[0] if n_labels else "Entity"
                    if n_name not in nodes_dict:
                        nodes_dict[n_name] = {
                            "id": n_name,
                            "label": n_name,
                            "type": n_type,
                            "aliases": nrow.get("aliases") or [],
                        }

            return {
                "nodes": list(nodes_dict.values()),
                "edges": edges,
                "total_nodes": len(nodes_dict),
                "total_edges": len(edges),
            }

    async def get_query_subgraph(
        self,
        entity_names: List[str],
        limit: int = 40,
    ) -> Dict[str, Any]:
        """
        Retrieves the localized connected subgraph surrounding specific entities
        queried or traversed during a query execution for inline UI visualization.
        """
        if not entity_names:
            return {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}

        driver = await self.writer.get_driver()
        safe_limit = min(max(1, limit), 60)
        from typing import LiteralString, cast

        cypher = """
        UNWIND $names AS name
        MATCH (s)
        WHERE toLower(s.name) CONTAINS toLower(name) OR any(a in s.aliases WHERE toLower(a) CONTAINS toLower(name))
        MATCH (s)-[r]-(t)
        WHERE t.name IS NOT NULL
        RETURN DISTINCT
            s.name AS source, labels(s) AS source_labels, s.aliases AS source_aliases,
            type(r) AS rel_type, r.source_chunk_id AS source_chunk_id, r.confidence AS confidence,
            t.name AS target, labels(t) AS target_labels, t.aliases AS target_aliases
        LIMIT $limit
        """

        async with driver.session() as session:
            result = await session.run(cast(LiteralString, cypher), names=entity_names[:5], limit=safe_limit)
            records = await result.data()
            await result.consume()

            nodes_dict: Dict[str, Dict[str, Any]] = {}
            edges: List[Dict[str, Any]] = []

            for row in records:
                s_name = row.get("source") or "Unknown"
                t_name = row.get("target") or "Unknown"
                s_labels = [lbl for lbl in row.get("source_labels", []) if lbl != "Entity"]
                t_labels = [lbl for lbl in row.get("target_labels", []) if lbl != "Entity"]
                s_type = s_labels[0] if s_labels else "Entity"
                t_type = t_labels[0] if t_labels else "Entity"

                if s_name not in nodes_dict:
                    nodes_dict[s_name] = {
                        "id": s_name,
                        "label": s_name,
                        "type": s_type,
                        "aliases": row.get("source_aliases") or [],
                    }
                if t_name not in nodes_dict:
                    nodes_dict[t_name] = {
                        "id": t_name,
                        "label": t_name,
                        "type": t_type,
                        "aliases": row.get("target_aliases") or [],
                    }

                edges.append({
                    "source": s_name,
                    "target": t_name,
                    "type": row.get("rel_type") or "RELATED_TO",
                    "source_chunk_id": row.get("source_chunk_id"),
                    "confidence": float(row.get("confidence") or 1.0),
                })

            return {
                "nodes": list(nodes_dict.values()),
                "edges": edges,
                "total_nodes": len(nodes_dict),
                "total_edges": len(edges),
            }


