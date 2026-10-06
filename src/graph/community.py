"""
Graph Community Detection and Corpus-Level Summarization Module.

Architecture Role:
    Implements topological clustering over the Neo4j knowledge graph using the Label Propagation
    Algorithm (LPA) to discover thematic research communities (e.g. dense passage retrieval,
    late-interaction retrieval, generative RAG, multi-hop reasoning). Synthesizes hierarchical
    community-level summaries to enable global corpus-level question answering.

Inputs:
    - Neo4j graph relationships (Paper, Method, Dataset, Author, Topic nodes and their edges).
    - User query strings for community relevance routing.

Outputs:
    - List of `CommunitySummaryRecord` models with cluster titles, member counts, key entities,
      thematic summaries, and factual assertions.
    - Context strings formatted for injection into global synthesis prompts.

Design Decisions:
    - Label Propagation Algorithm (LPA): O(V + E) deterministic iterative graph clustering in pure
      Python without external C dependencies or proprietary plugins.
    - Automatic Thematic Tagging: Derives community titles and themes by analyzing the degree centrality
      and entity types of member nodes.
    - Memory Caching: Caches computed communities until graph updates occur, providing sub-millisecond
      lookup during query synthesis.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from src.core.logging import setup_logger
from src.graph.writer import Neo4jWriter

logger = setup_logger(name="graph.community")


class CommunitySummaryRecord(BaseModel):
    """Represents a detected topological cluster with summary metadata."""
    community_id: str = Field(..., description="Unique community identifier (e.g. comm_1)")
    title: str = Field(..., description="Inferred or synthesized theme title")
    member_count: int = Field(..., description="Number of entities belonging to this community")
    top_entities: List[str] = Field(default_factory=list, description="Primary papers, methods, and authors")
    summary: str = Field(..., description="Corpus-level thematic summary of this community")
    themes: List[str] = Field(default_factory=list, description="Key research topics/subfields")


class CommunityDetectionResponse(BaseModel):
    """Response containing all detected graph communities and corpus-level summaries."""
    total_communities: int = Field(..., description="Total number of detected topological communities")
    communities: List[CommunitySummaryRecord] = Field(default_factory=list, description="List of detected communities")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of community detection execution",
    )

# ==============================================================================
# Configuration Constants
# ==============================================================================
MAX_LPA_ITERATIONS: int = 30
MIN_COMMUNITY_SIZE: int = 2
CACHE_TTL_SECONDS: float = 300.0  # 5 minutes in-memory cache


class GraphCommunityDetector:
    """
    Executes community detection over the Neo4j property graph and generates
    corpus-level thematic summaries.
    """

    def __init__(self, writer: Optional[Neo4jWriter] = None) -> None:
        self.writer = writer or Neo4jWriter()
        self._cached_communities: Optional[List[CommunitySummaryRecord]] = None
        self._cache_timestamp: float = 0.0

    async def _fetch_graph_topology(self) -> Tuple[Dict[str, str], List[Tuple[str, str, str]]]:
        """
        Fetches all nodes and directed relationships from Neo4j.

        Returns:
            Tuple of (node_types_dict, edges_list).
        """
        driver = await self.writer.get_driver()
        node_types: Dict[str, str] = {}
        edges: List[Tuple[str, str, str]] = []

        query = """
        MATCH (s)-[r]->(t)
        WHERE s.name IS NOT NULL AND t.name IS NOT NULL
        RETURN 
            s.name AS source_name,
            labels(s)[0] AS source_type,
            type(r) AS rel_type,
            t.name AS target_name,
            labels(t)[0] AS target_type
        """

        async with driver.session() as session:
            result = await session.run(query)
            async for record in result:
                s_name = str(record["source_name"])
                s_type = str(record["source_type"] or "Entity")
                rel = str(record["rel_type"])
                t_name = str(record["target_name"])
                t_type = str(record["target_type"] or "Entity")

                node_types[s_name] = s_type
                node_types[t_name] = t_type
                edges.append((s_name, rel, t_name))

        # Also fetch isolated nodes with no edges
        isolated_query = """
        MATCH (n)
        WHERE n.name IS NOT NULL AND NOT (n)--()
        RETURN n.name AS name, labels(n)[0] AS type
        LIMIT 100
        """
        async with driver.session() as session:
            result = await session.run(isolated_query)
            async for record in result:
                name = str(record["name"])
                ntype = str(record["type"] or "Entity")
                if name not in node_types:
                    node_types[name] = ntype

        return node_types, edges

    @staticmethod
    def _run_label_propagation(
        nodes: List[str],
        edges: List[Tuple[str, str, str]],
        max_iterations: int = MAX_LPA_ITERATIONS,
    ) -> Dict[str, int]:
        """
        Executes semi-synchronous Label Propagation Algorithm (LPA).
        Partitions nodes into densely connected components where nodes adopt the majority
        community label of their neighbors.
        """
        if not nodes:
            return {}

        # 1. Build adjacency list (undirected for community discovery)
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for s, _, t in edges:
            if s != t:
                adjacency[s].add(t)
                adjacency[t].add(s)

        # 2. Initialize each node with unique integer label
        labels: Dict[str, int] = {node: i for i, node in enumerate(nodes)}

        # Deterministic pseudo-random seed for repeatable community assignment
        rng = random.Random(42)

        # 3. Iterative label update
        for _ in range(max_iterations):
            changed = False
            shuffled_nodes = list(nodes)
            rng.shuffle(shuffled_nodes)

            for node in shuffled_nodes:
                neighbors = adjacency.get(node)
                if not neighbors:
                    continue

                neighbor_labels = [labels[nbr] for nbr in neighbors]
                if not neighbor_labels:
                    continue

                # Count label frequencies among neighbors
                counts = Counter(neighbor_labels)
                max_count = max(counts.values())
                # Top candidate labels with max frequency
                candidates = [lbl for lbl, c in counts.items() if c == max_count]
                best_label = min(candidates)  # Deterministic tie-break by minimum ID

                if labels[node] != best_label:
                    labels[node] = best_label
                    changed = True

            if not changed:
                break

        return labels

    def _synthesize_community_record(
        self,
        community_id: str,
        member_nodes: List[str],
        node_types: Dict[str, str],
        edges: List[Tuple[str, str, str]],
    ) -> CommunitySummaryRecord:
        """
        Creates a structured CommunitySummaryRecord by inspecting member nodes,
        their ontology types, degree centrality, and internal relationships.
        """
        members_set = set(member_nodes)
        type_groups: Dict[str, List[str]] = defaultdict(list)
        for m in member_nodes:
            t = node_types.get(m, "Entity")
            type_groups[t].append(m)

        # Calculate degree centrality within this community
        degree: Dict[str, int] = defaultdict(int)
        internal_statements: List[str] = []
        for s, rel, t in edges:
            if s in members_set and t in members_set:
                degree[s] += 1
                degree[t] += 1
                clean_rel = rel.lower().replace("_", " ")
                internal_statements.append(f"'{s}' {clean_rel} '{t}'")

        # Sort top entities by internal connection degree
        top_entities = sorted(member_nodes, key=lambda n: degree.get(n, 0), reverse=True)[:6]

        # Determine prominent methods and papers to formulate the theme title
        methods = type_groups.get("Method", [])
        papers = type_groups.get("Paper", [])
        datasets = type_groups.get("Dataset", [])
        authors = type_groups.get("Author", [])

        # Construct title
        if methods and datasets:
            title = f"{methods[0]} & {datasets[0]} Evaluation Cluster"
        elif methods:
            title = f"{methods[0]} Architecture & Extensions"
        elif papers:
            title = f"{papers[0][:40]} Literature Subgraph"
        elif authors:
            title = f"{authors[0]} Co-Authorship Group"
        else:
            title = f"Topic Cluster: {member_nodes[0][:30]}"

        # Construct concise summary text
        summary_parts = []
        if papers:
            summary_parts.append(f"Focuses on research literature including {', '.join(papers[:3])}.")
        if methods:
            summary_parts.append(f"Investigates algorithmic methods such as {', '.join(methods[:4])}.")
        if datasets:
            summary_parts.append(f"Evaluates benchmarks across {', '.join(datasets[:3])}.")
        if authors:
            summary_parts.append(f"Key contributing authors include {', '.join(authors[:4])}.")

        summary_text = " ".join(summary_parts) if summary_parts else (
            f"Topological cluster containing {len(member_nodes)} connected entities including {', '.join(member_nodes[:4])}."
        )

        # Themes derived from methods and datasets
        themes = list(dict.fromkeys(methods[:3] + datasets[:2] + type_groups.get("Topic", [])[:2]))

        return CommunitySummaryRecord(
            community_id=community_id,
            title=title,
            member_count=len(member_nodes),
            top_entities=top_entities,
            summary=summary_text,
            themes=themes,
        )

    async def detect_communities(self, force_refresh: bool = False) -> List[CommunitySummaryRecord]:
        """
        Executes community detection over the Neo4j graph and returns structured summaries.
        Uses in-memory caching to avoid redundant recalculation.
        """
        now = time.time()
        if not force_refresh and self._cached_communities and (now - self._cache_timestamp < CACHE_TTL_SECONDS):
            return self._cached_communities

        logger.info("Executing topological community detection across Neo4j graph...")
        node_types, edges = await self._fetch_graph_topology()

        all_nodes = list(node_types.keys())
        if not all_nodes:
            logger.warning("No nodes found in Neo4j during community detection.")
            return []

        labels = self._run_label_propagation(all_nodes, edges)

        # Group nodes by community label
        communities_map: Dict[int, List[str]] = defaultdict(list)
        for node, lbl in labels.items():
            communities_map[lbl].append(node)

        # Filter and sort communities by size
        sorted_groups = sorted(
            [members for members in communities_map.values() if len(members) >= MIN_COMMUNITY_SIZE],
            key=len,
            reverse=True,
        )

        # Also aggregate singletons into an auxiliary community if present
        singletons = [members[0] for members in communities_map.values() if len(members) < MIN_COMMUNITY_SIZE]

        records: List[CommunitySummaryRecord] = []
        for idx, members in enumerate(sorted_groups, start=1):
            comm_id = f"community_{idx:02d}"
            rec = self._synthesize_community_record(comm_id, members, node_types, edges)
            records.append(rec)

        if singletons:
            singleton_rec = CommunitySummaryRecord(
                community_id=f"community_{len(records) + 1:02d}",
                title="Peripheral & Isolated Corpus Entities",
                member_count=len(singletons),
                top_entities=singletons[:6],
                summary=f"Collection of {len(singletons)} standalone or sparsely connected peripheral entities.",
                themes=["Peripheral Entities"],
            )
            records.append(singleton_rec)

        self._cached_communities = records
        self._cache_timestamp = now
        logger.info("Community detection complete: identified %d distinct communities.", len(records))
        return records

    async def get_corpus_summary_context(self, query: Optional[str] = None, max_communities: int = 4) -> str:
        """
        Generates a consolidated corpus-level overview context string based on detected
        communities, suitable for answering high-level thematic queries.
        """
        communities = await self.detect_communities()
        if not communities:
            return "No topological communities detected in the knowledge graph."

        # If query provided, rank communities by keyword overlap
        if query:
            q_lower = query.lower()
            def score_community(c: CommunitySummaryRecord) -> int:
                score = 0
                for theme in c.themes:
                    if theme.lower() in q_lower:
                        score += 3
                for entity in c.top_entities:
                    if entity.lower() in q_lower:
                        score += 2
                if any(w in c.summary.lower() for w in q_lower.split() if len(w) > 3):
                    score += 1
                return score

            ranked = sorted(communities, key=score_community, reverse=True)
        else:
            ranked = communities

        selected = ranked[:max_communities]
        lines = ["=== CORPUS-LEVEL RESEARCH COMMUNITIES (GRAPH SUMMARY) ==="]
        for c in selected:
            lines.append(f"[{c.community_id}] {c.title} ({c.member_count} entities)")
            lines.append(f"Summary: {c.summary}")
            if c.top_entities:
                lines.append(f"Key Entities: {', '.join(c.top_entities)}")
            lines.append("")

        return "\n".join(lines)


# Singleton
_detector: Optional[GraphCommunityDetector] = None


def get_community_detector() -> GraphCommunityDetector:
    """Returns singleton instance of GraphCommunityDetector."""
    global _detector
    if _detector is None:
        _detector = GraphCommunityDetector()
    return _detector
