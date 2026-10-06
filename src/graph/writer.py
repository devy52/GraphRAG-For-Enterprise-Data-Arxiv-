"""
Neo4j Graph Database Writer Module.

Architecture Role:
    Part of Phase 2 (Knowledge Graph Ingestion). Persists resolved entities and factual
    relationships from `EntityResolver` into Neo4j Community Edition with APOC.
    Builds the structural backbone used by the parameterized query engine (Phase 4)
    to traverse multi-hop citation chains, method extensions, and benchmark comparisons.

Inputs:
    - `ResolvedEntity` models containing canonical names and accumulated aliases.
    - `ExtractedFact` models containing canonical triples, relationship types, and `source_chunk_id` keys.

Outputs:
    - Directed property graph nodes and edges stored in Neo4j.
    - Idempotent schema constraints ensuring unique node creation.

Design Decisions & Invariants:
    - Idempotency via MERGE: Re-running ingestion over the same corpus never creates duplicate nodes or edges.
    - Uniqueness Constraints: Enforced on `(n:EntityType.name)` to guarantee sub-millisecond lookups.
    - Atomic Single-Roundtrip MERGE: Merges source node, target node, and directed relationship
      in a single Cypher query to avoid partial write inconsistencies.
    - Chunk-Level Grounding: Every relationship edge carries a `source_chunk_id` property,
      enabling downstream answer synthesis to fetch the exact source text passage for citations.
    - Async Driver & Stream Consumption: Calls `await result.consume()` after every query execution
      to ensure results are fully received from the Neo4j socket and prevent unconsumed buffer leaks.
    - PEP 675 Type Safety: Uses `typing.cast(LiteralString, ...)` on dynamically generated Cypher strings
      to satisfy modern static type checkers.
"""

import asyncio
from typing import Any, Callable, List, LiteralString, Optional, cast
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.models import EntityType, ExtractedFact, ResolvedEntity

logger = setup_logger(name="graph.writer")


class Neo4jWriter:
    """
    Manages schema constraints, indexes, and idempotent atomic writes to Neo4j.
    Equipped with self-healing connection recycling for sleep/network recovery.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.uri = uri or self.settings.neo4j_uri
        self.user = user or self.settings.neo4j_user
        self.password = password or self.settings.neo4j_password
        self._driver: Optional[AsyncDriver] = None

    async def get_driver(self) -> AsyncDriver:
        """Initializes or returns the active Neo4j async driver instance."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                liveness_check_timeout=2.0,  # Proactively test socket liveness
                max_connection_lifetime=300,  # 5 minutes
                keep_alive=True,
                auth=(self.user, self.password),
            )
        return self._driver

    async def close(self) -> None:
        """Closes the active Neo4j driver connection pool."""
        if self._driver is not None:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None

    async def _execute_with_retry(self, operation_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Executes a database write with self-healing exponential backoff.
        Automatically recycles defunct Bolt sockets if dropped by laptop sleep or NAT proxy.
        """
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                return await operation_fn(*args, **kwargs)
            except (ServiceUnavailable, SessionExpired, TimeoutError, ConnectionResetError, OSError) as exc:
                logger.warning(
                    "Neo4j connection error (attempt %d/%d): %s. Recycling driver pool and retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                await self.close()
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2.0 * attempt)

    async def init_schema(self) -> None:
        """
        Initializes uniqueness constraints and indexes for all entity types in Docs/ONTOLOGY.md.

        Workflow:
        1. Iterates over all `EntityType` enum members (Paper, Author, Method, Dataset, etc.).
        2. Creates a named uniqueness constraint `constraint_{entity}_name_uniq` if not already present.
        3. Awaits `result.consume()` to commit the schema change and flush the driver buffer.
        """
        # Step 1: Acquire async driver instance and open a managed session
        driver = await self.get_driver()
        async with driver.session() as session:
            # Step 2: Iterate through every ontology entity type to build constraints
            for entity_type in EntityType:
                constraint_name = f"constraint_{entity_type.value.lower()}_name_uniq"
                constraint_query = (
                    f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                    f"FOR (n:{entity_type.value}) REQUIRE n.name IS UNIQUE"
                )
                try:
                    # Step 3: Execute CREATE CONSTRAINT with cast for PEP 675 type safety
                    result = await session.run(cast(LiteralString, constraint_query))
                    # Step 4: Consume result to ensure the schema change commits immediately
                    await result.consume()
                    logger.debug("Ensured uniqueness constraint: %s", constraint_name)
                except Exception as exc:
                    logger.warning("Constraint creation notice on %s: %s", entity_type.value, exc)

        logger.info("Initialized Neo4j schema constraints and indexes successfully.")

    async def initialize(self) -> None:
        """Initializes Neo4j schema constraints and indexes."""
        await self.init_schema()

    async def _write_entities_batch(self, entities: List[ResolvedEntity]) -> None:
        if not entities:
            return

        driver = await self.get_driver()
        async with driver.session() as session:
            for entity in entities:
                query = (
                    f"MERGE (n:{entity.entity_type.value} {{name: $canonical_name}}) "
                    f"ON CREATE SET n.aliases = $aliases, n.created_at = timestamp() "
                    f"ON MATCH SET n.aliases = [a IN coalesce(n.aliases, []) WHERE a IS NOT NULL] + [b IN $aliases WHERE NOT b IN coalesce(n.aliases, [])]"
                )
                result = await session.run(
                    cast(LiteralString, query),
                    canonical_name=entity.canonical_name,
                    aliases=entity.aliases,
                )
                await result.consume()

        logger.info("Wrote %d resolved entity nodes to Neo4j", len(entities))

    async def write_entities(self, entities: List[ResolvedEntity]) -> None:
        """Idempotently creates or updates entity nodes with auto-healing retry."""
        await self._execute_with_retry(self._write_entities_batch, entities)

    async def _write_facts_batch(self, facts: List[ExtractedFact]) -> None:
        if not facts:
            return

        driver = await self.get_driver()
        async with driver.session() as session:
            for fact in facts:
                atomic_merge_query = (
                    f"MERGE (s:{fact.source_type.value} {{name: $source_name}}) "
                    f"MERGE (t:{fact.target_type.value} {{name: $target_name}}) "
                    f"MERGE (s)-[r:{fact.relation.value} {{source_chunk_id: $chunk_id}}]->(t) "
                    f"ON CREATE SET r.confidence = $confidence, r.created_at = timestamp()"
                )
                result = await session.run(
                    cast(LiteralString, atomic_merge_query),
                    source_name=fact.source_name,
                    target_name=fact.target_name,
                    chunk_id=fact.source_chunk_id,
                    confidence=fact.confidence,
                )
                await result.consume()

        logger.info("Wrote %d relational edges to Neo4j", len(facts))

    async def write_facts(self, facts: List[ExtractedFact]) -> None:
        """Idempotently writes directed relationships with auto-healing retry."""
        await self._execute_with_retry(self._write_facts_batch, facts)

    async def delete_edges_for_chunks(self, chunk_ids: List[str]) -> int:
        """
        Deletes all relationship edges associated with specific source_chunk_ids.
        Used during incremental updates to purge stale or modified chunks.
        """
        if not chunk_ids:
            return 0
        driver = await self.get_driver()
        cypher = """
        UNWIND $chunk_ids AS cid
        MATCH ()-[r]->()
        WHERE r.source_chunk_id = cid
        DELETE r
        RETURN count(r) AS deleted_count
        """
        async with driver.session() as session:
            result = await session.run(cast(LiteralString, cypher), chunk_ids=chunk_ids)
            record = await result.single()
            await result.consume()
            count = record["deleted_count"] if record else 0
            logger.info("Deleted %d stale relationship edges from Neo4j for %d chunks", count, len(chunk_ids))
            return count

    async def clear_database(self) -> None:
        """
        Clears all nodes and relationships (Used for clean unit testing and benchmarks).
        """

        # Step 1: Acquire async driver instance and session
        driver = await self.get_driver()
        async with driver.session() as session:
            # Step 2: Execute DETACH DELETE to wipe all nodes and connected edges
            result = await session.run("MATCH (n) DETACH DELETE n")
            # Step 3: Consume result to confirm completion
            await result.consume()
        logger.warning("Cleared all nodes and relationships from Neo4j.")
