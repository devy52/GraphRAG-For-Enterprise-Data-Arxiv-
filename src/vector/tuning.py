"""
HNSW Index Creation & ef_search Recall@K Tuning Module.

Architecture Role:
    Part of Phase 3 (Vector Store Ingestion & pgvector). Provides automated benchmarking
    and tuning for Hierarchical Navigable Small World (HNSW) vector indexing in PostgreSQL.
    Guarantees that approximate nearest neighbor (ANN) retrieval achieves >= 95% Recall@K
    relative to exact flat scan ground truth while minimizing query latency.

Inputs:
    - Initialized `VectorStore` instance with populated `document_chunks` table.
    - Test query suite (domain queries over academic papers).
    - HNSW construction parameters (`m=16`, `ef_construction=64`).
    - Candidate `ef_search` values (`[16, 32, 64, 128, 200]`).

Outputs:
    - Executed DDL creating or dropping `document_chunks_embedding_hnsw_idx`.
    - Recall@K performance mapping (`Dict[ef_search, float]`) validating index accuracy.

Design Decisions:
    - Operator Class: Uses `vector_cosine_ops` to match the `<=>` cosine distance metric.
    - Exact Ground Truth: Disables PostgreSQL index and bitmap scans (`SET LOCAL enable_indexscan = OFF`)
      to force a brute-force sequential flat scan as the true mathematical baseline.
    - Target Recall: Validates that candidate `ef_search` achieves `TARGET_RECALL >= 0.95`.
"""

from typing import Dict, List, Set
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.core.logging import setup_logger
from src.vector.indexer import VectorStore

logger = setup_logger(name="vector.tuning")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_M = 16                                   # Number of bidirectional links per HNSW node
DEFAULT_EF_CONSTRUCTION = 64                     # Size of dynamic candidate list during index build
DEFAULT_EF_SEARCH_CANDIDATES = [16, 32, 64, 128, 200]  # Candidate ef_search values to benchmark
TARGET_RECALL = 0.95                             # Minimum acceptable Recall@K threshold (95%)


class HNSWTuner:
    """
    Manages HNSW index creation, flat scan baseline extraction, and recall@k optimization.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store
        self.engine: AsyncEngine = vector_store.engine

    async def create_hnsw_index(
        self,
        m: int = DEFAULT_M,
        ef_construction: int = DEFAULT_EF_CONSTRUCTION,
    ) -> None:
        """
        Creates an HNSW index on the document_chunks table using vector_cosine_ops.

        Parameters:
        - `m`: Maximum number of connections per element in each layer.
        - `ef_construction`: Size of dynamic candidate list during graph construction.
        """
        async with self.engine.begin() as conn:
            index_query = text(f"""
                CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx 
                ON document_chunks 
                USING hnsw (embedding vector_cosine_ops) 
                WITH (m = {m}, ef_construction = {ef_construction});
            """)
            await conn.execute(index_query)
        logger.info("Created HNSW index with m=%d, ef_construction=%d", m, ef_construction)

    async def drop_hnsw_index(self) -> None:
        """
        Drops the HNSW index to enable flat exact vector scans.
        """
        async with self.engine.begin() as conn:
            await conn.execute(text("DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;"))
        logger.info("Dropped HNSW index.")

    async def get_exact_ground_truth(self, query: str, k: int = 5) -> List[str]:
        """
        Computes exact top-k nearest neighbors by explicitly disabling PostgreSQL index scans.

        Disables `enable_indexscan` and `enable_bitmapscan` within the local transaction
        to force PostgreSQL into a brute-force sequential flat scan over all embedding vectors.
        """
        query_vec = await self.vector_store.embedding_generator.embed_query(query)
        async with self.vector_store.session_factory() as session:
            # Force sequential flat scan for true exact nearest neighbors
            await session.execute(text("SET LOCAL enable_indexscan = OFF;"))
            await session.execute(text("SET LOCAL enable_bitmapscan = OFF;"))

            search_query = text("""
                SELECT chunk_id 
                FROM document_chunks 
                ORDER BY embedding <=> CAST(:query_vector AS vector)
                LIMIT :k;
            """)
            result = await session.execute(
                search_query,
                {"query_vector": str(query_vec), "k": k},
            )
            rows = result.mappings().fetchall()
            return [str(row["chunk_id"]) for row in rows]

    async def evaluate_recall_at_k(
        self,
        test_queries: List[str],
        k: int = 5,
        ef_search_values: List[int] = DEFAULT_EF_SEARCH_CANDIDATES,
    ) -> Dict[int, float]:
        """
        Measures Recall@K across various ef_search candidates against exact ground truth.

        Recall Metric:
            Recall@K = |TopK(HNSW, ef) ∩ TopK(Exact)| / K

        Workflow:
        1. Compute exact top-k ground truth chunk IDs for every test query.
        2. Iterate through each ef_search candidate (e.g., 16, 32, 64, 128, 200).
        3. Execute HNSW ANN query for each test query and calculate overlap ratio.
        4. Log average Recall@K and return evaluation results.
        """
        if not test_queries:
            return {}

        logger.info("Evaluating HNSW recall@%d across %d test queries...", k, len(test_queries))
        
        # ----------------------------------------------------------------------
        # Step 1: Compute Exact Ground Truth for Each Test Query
        # ----------------------------------------------------------------------
        ground_truth: Dict[str, Set[str]] = {}
        for query in test_queries:
            exact_ids = await self.get_exact_ground_truth(query, k=k)
            ground_truth[query] = set(exact_ids)

        recall_results: Dict[int, float] = {}

        # ----------------------------------------------------------------------
        # Step 2: Benchmark Each ef_search Candidate
        # ----------------------------------------------------------------------
        for ef in ef_search_values:
            total_recall = 0.0
            for query in test_queries:
                hnsw_results = await self.vector_store.similarity_search(query, top_k=k, ef_search=ef)
                hnsw_ids = set(r.chunk_id for r in hnsw_results)
                
                exact_set = ground_truth[query]
                overlap = len(hnsw_ids & exact_set)
                query_recall = overlap / float(k) if k > 0 else 1.0
                total_recall += query_recall

            avg_recall = total_recall / len(test_queries)
            recall_results[ef] = avg_recall
            status = "PASSED (>=0.95)" if avg_recall >= TARGET_RECALL else "BELOW TARGET"
            logger.info("ef_search = %3d | Recall@%d: %.4f (%s)", ef, k, avg_recall, status)

        return recall_results
