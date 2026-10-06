"""
Normalized Query & Response Cache Module.

Architecture Role:
    Part of Phase 6 (Synthesis & Strict Citation Validation). Provides deterministic caching of
    synthesized, citation-validated responses keyed by canonicalized query hash (SHA-256).
    Significantly minimizes LLM inference latency and token expenditure for repeated queries across sessions.

Inputs:
    - Raw user query strings.
    - Synthesized responses and citation metadata.

Outputs:
    - Cached response objects on cache hits.
    - Hit/miss statistics and cache eviction controls.

Design Decisions:
    - Canonical Query Normalization: Lowercases, strips punctuation, and collapses whitespace before
      computing the SHA-256 digest to maximize cache hit rate across semantically identical queries.
    - Memory-Bounded LRU Strategy: Evicts the least recently accessed entries when reaching max capacity.
"""

from collections import OrderedDict
import hashlib
import re
import threading
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

from src.core.logging import setup_logger

logger = setup_logger(name="core.cache")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_CACHE_MAX_ENTRIES = 1000   # Maximum number of query-response entries to retain in memory


class CacheStats(BaseModel):
    """
    Diagnostic metrics tracking cache efficiency.
    """
    total_requests: int = Field(default=0, description="Total cache lookup operations")
    hits: int = Field(default=0, description="Number of successful cache hits")
    misses: int = Field(default=0, description="Number of cache misses")
    size: int = Field(default=0, description="Current number of stored items in cache")

    @property
    def hit_rate(self) -> float:
        """Computes hit rate percentage."""
        return (self.hits / self.total_requests) if self.total_requests > 0 else 0.0


class QueryResponseCache:
    """
    Thread-safe LRU response cache keyed by canonical SHA-256 query digests.
    """

    def __init__(self, max_entries: int = DEFAULT_CACHE_MAX_ENTRIES) -> None:
        self.max_entries = max_entries
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.stats = CacheStats()

    @staticmethod
    def normalize_query(query: str) -> str:
        """
        Normalizes query string by trimming, lowercasing, and collapsing whitespace.
        """
        # Step 1: Lowercase and strip leading/trailing whitespace
        clean = query.lower().strip()
        # Step 2: Collapse consecutive whitespace characters
        clean = re.sub(r"\s+", " ", clean)
        # Step 3: Strip trailing punctuation (?, !, .)
        clean = clean.rstrip("?!.")
        return clean

    @classmethod
    def compute_key(cls, query: str) -> str:
        """
        Computes the SHA-256 digest of the canonicalized query string.
        """
        normalized = cls.normalize_query(query)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        """
        Retrieves a cached value for the given query, updating LRU recency.
        """
        key = self.compute_key(query)
        with self._lock:
            self.stats.total_requests += 1
            if key in self._cache:
                # Mark as recently used by moving to the end of the OrderedDict
                self._cache.move_to_end(key)
                self.stats.hits += 1
                logger.debug("Cache HIT for query hash: %s", key[:12])
                return self._cache[key]

            self.stats.misses += 1
            logger.debug("Cache MISS for query hash: %s", key[:12])
            return None

    def set(self, query: str, value: Any) -> None:
        """
        Stores an item in the cache, evicting the oldest item if capacity is exceeded.
        """
        key = self.compute_key(query)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value

            # Enforce max capacity by popping the oldest (first) item
            if len(self._cache) > self.max_entries:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("Evicted oldest cache item: %s", evicted_key[:12])

            self.stats.size = len(self._cache)

    def clear(self) -> None:
        """Clears all stored entries from cache."""
        with self._lock:
            self._cache.clear()
            self.stats = CacheStats()
            logger.info("Cleared QueryResponseCache.")

    def size(self) -> int:
        """Returns the number of entries currently stored."""
        with self._lock:
            return len(self._cache)
