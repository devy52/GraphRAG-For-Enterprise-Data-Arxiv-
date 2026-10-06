from __future__ import annotations

import math
import re
from typing import Any, Optional

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _lexical_overlap(a: str, b: str) -> float:
    """Jaccard word overlap — a cheap, honest heuristic, not a semantic
    measure. Good enough to flag 'this chunk shares essentially no
    vocabulary with the output', not precise enough to claim more than that."""
    words_a, words_b = _words(a), _words(b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _extract_chunk_ids(context_item: str, relevant: set[str]) -> list[str]:
    """Extracts explicit chunk identifiers from a retrieved context entry.

    Handles GraphRAG provenance formats:
    - '[graph] ... [chunk: chunk_id]'
    - '[retrieved] ... [chunk_id]'
    - Direct chunk ID string matching relevant ground truth.
    """
    if context_item in relevant:
        return [context_item]

    # Pattern 1: explicit graph/vector citation marker like [chunk: <id>]
    cids = re.findall(r"\[chunk:\s*([a-zA-Z0-9_\-\.]+)\]", context_item)
    if cids:
        return cids

    # Pattern 2: bracketed chunk ID [chunk_...]
    bracketed = re.findall(r"\[([a-zA-Z0-9_\-\.]+)\]", context_item)
    valid_bracketed = [
        cid for cid in bracketed
        if cid in relevant or cid.startswith("chunk_") or cid.startswith("doc_")
    ]
    if valid_bracketed:
        return valid_bracketed

    # Pattern 3: exact match on known relevant with word boundary
    found = [rel for rel in relevant if re.search(rf"\b{re.escape(rel)}\b", context_item)]
    if found:
        return found

    # Pattern 4: the item itself is an identifier or standalone string
    return [context_item]


class RetrievalEvaluator(BaseEvaluator):
    """Deterministic retrieval-quality metrics. No LLM calls, no dependencies.

    precision_at_k, recall_at_k, mrr, and ndcg_at_k require ground truth: each dataset
    example's `metadata.relevant_chunks` — a list of strings that must
    EXACTLY match entries in `context` to count as relevant.

    chunk_utilization needs no ground truth — it's a lexical-overlap
    heuristic between each retrieved chunk and the final output.
    """

    ALL_METRICS = ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k", "chunk_utilization")

    METRIC_DESCRIPTIONS = {
        "precision_at_k": (
            "Fraction of retrieved chunks (top-K) that are in metadata.relevant_chunks "
            "(exact string match). Requires ground truth in the dataset."
        ),
        "recall_at_k": (
            "Fraction of all relevant chunks that were retrieved in top-K. "
            "Requires metadata.relevant_chunks in the dataset."
        ),
        "mrr": (
            "1 / rank of the first relevant chunk in the retrieved list (0 if none found). "
            "Requires metadata.relevant_chunks in the dataset."
        ),
        "ndcg_at_k": (
            "Normalized Discounted Cumulative Gain at rank K. Computes position-discounted "
            "relevance gain normalized by ideal DCG. Supports binary or graded relevance."
        ),
        "chunk_utilization": (
            "Heuristic: fraction of retrieved chunks with meaningful word-overlap with the "
            "output — an approximation of whether the generator used what was retrieved, "
            "not a precise measure. Needs no ground truth."
        ),
    }

    def __init__(
        self,
        judge: Optional[BaseJudgeBackend] = None,  # unused — this evaluator is fully deterministic
        metrics: Optional[list[str]] = None,
        k: Optional[int] = None,
        chunk_utilization_threshold: float = 0.15,
    ) -> None:
        self.metrics = metrics or list(self.ALL_METRICS)
        self.k = k
        self.chunk_utilization_threshold = chunk_utilization_threshold

    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        context = context or []
        scores: dict[str, float] = {}

        ranking_metrics = {"precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"} & set(self.metrics)
        if ranking_metrics:
            relevant = set(
                (metadata or {}).get("relevant_chunks", [])
                or (metadata or {}).get("gold_chunk_ids", [])
            )
            if relevant:
                # Deduplicate source chunk IDs preserving first-seen ranking order
                unique_retrieved_ids: list[str] = []
                for c in context:
                    ids = _extract_chunk_ids(c, relevant)
                    for cid in ids:
                        if cid not in unique_retrieved_ids:
                            unique_retrieved_ids.append(cid)

                k = self.k or len(unique_retrieved_ids)
                retrieved_at_k = unique_retrieved_ids[:k]
                hits_at_k = [cid for cid in retrieved_at_k if cid in relevant]

                if "precision_at_k" in self.metrics and retrieved_at_k:
                    scores["precision_at_k"] = len(hits_at_k) / len(retrieved_at_k)
                if "recall_at_k" in self.metrics:
                    scores["recall_at_k"] = len(hits_at_k) / len(relevant)
                if "mrr" in self.metrics:
                    rank = next(
                        (i + 1 for i, cid in enumerate(retrieved_at_k) if cid in hits_at_k), None
                    )
                    scores["mrr"] = (1.0 / rank) if rank else 0.0
                if "ndcg_at_k" in self.metrics:
                    graded_scores = (metadata or {}).get("relevance_scores", {})
                    dcg = 0.0
                    for i, cid in enumerate(retrieved_at_k):
                        rel = float(graded_scores.get(cid, 1.0 if cid in hits_at_k else 0.0))
                        dcg += (2.0 ** rel - 1.0) / math.log2(i + 2)
                    if graded_scores:
                        ideal_rels = sorted([float(v) for v in graded_scores.values()], reverse=True)[:k]
                    else:
                        ideal_rels = [1.0] * min(k, len(relevant))
                    idcg = sum((2.0 ** rel - 1.0) / math.log2(i + 2) for i, rel in enumerate(ideal_rels))
                    scores["ndcg_at_k"] = min(1.0, (dcg / idcg) if idcg > 0 else 0.0)
            # no relevant_chunks in metadata -> silently skip these ranking metrics,
            # not an error: most datasets won't have ranked ground truth on day one

        if "chunk_utilization" in self.metrics and context:
            used = sum(
                1 for c in context if _lexical_overlap(c, output) >= self.chunk_utilization_threshold
            )
            scores["chunk_utilization"] = used / len(context)

        return scores
