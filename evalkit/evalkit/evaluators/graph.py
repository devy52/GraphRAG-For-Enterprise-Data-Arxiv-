from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from evalkit.contracts.evaluator import BaseEvaluator
from evalkit.contracts.judge_backend import BaseJudgeBackend

_COMMUNITY_COHERENCE_PROMPT = """You are grading whether a GraphRAG community summary coherently and \
accurately represents its underlying member data points without hallucinating external associations.

Member data / grouped chunks:
{community_context}

Community summary:
{summary}

Score community coherence from 0.0 (incoherent, hallucinates non-existent connections or contradicts member data) \
to 1.0 (faithfully and coherently synthesizes member entities and relationships). \
Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""

_ENTITY_RELATION_COVERAGE_PROMPT = """You are grading entity and relation extraction coverage. Assess whether \
the extracted graph elements capture all key entities and relationships present in the source text.

Source text / reference:
{reference}

Extracted graph elements:
{extracted_elements}

Score coverage from 0.0 (missed all key entities and relationships) to 1.0 (captured all critical entities and relationships). \
Respond with a JSON object containing `score` (0.0-1.0) and brief `reasoning`."""


def compute_lexical_diversity(text: str) -> float:
    """Computes distinct unigram and bigram diversity score in [0.0, 1.0]."""
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.0
    if len(words) == 1:
        return 1.0

    unigram_ratio = len(set(words)) / len(words)
    bigrams = list(zip(words[:-1], words[1:]))
    bigram_ratio = len(set(bigrams)) / len(bigrams) if bigrams else 1.0

    return round(0.5 * unigram_ratio + 0.5 * bigram_ratio, 4)


def compute_thematic_coverage(text: str, expected_themes: Sequence[str]) -> float:
    """Computes fraction of expected themes/entities appearing in text."""
    if not expected_themes:
        return 1.0
    text_lower = text.lower()
    covered = sum(1 for theme in expected_themes if theme.lower() in text_lower)
    return round(covered / len(expected_themes), 4)


def compute_graph_utilization_rate(
    output: str,
    graph_facts_retrieved: Optional[Sequence[str]] = None,
    graph_facts_used: Optional[Sequence[str]] = None,
    citations: Optional[Sequence[str]] = None,
) -> float:
    """Computes the fraction of retrieved graph elements utilized in the answer.

    If explicit `graph_facts_used` is given, uses len(used) / len(retrieved).
    Otherwise, checks which retrieved graph fact entities or statements appear in `output`.
    """
    if not graph_facts_retrieved:
        return 0.0

    total_facts = len(graph_facts_retrieved)
    if total_facts == 0:
        return 0.0

    if graph_facts_used is not None:
        used_count = len(graph_facts_used)
        return min(1.0, max(0.0, round(used_count / total_facts, 4)))

    # If the answer is an explicit refusal or abstention, no graph facts were utilized
    output_lower = output.lower()
    refusal_markers = (
        "insufficient evidence",
        "not enough information",
        "provided context does not contain",
        "provided context does not provide",
        "cannot be determined",
        "cannot determine",
        "i do not have enough",
        "no evidence",
    )
    if any(marker in output_lower for marker in refusal_markers):
        return 0.0

    # Fallback heuristic: check which retrieved statements or their entity anchors appear in output
    matched_count = 0
    for fact in graph_facts_retrieved:
        fact_str = str(fact).strip()
        # Clean Cypher statement syntax like `(Paper:X)-[:USES]->(Method:Y)`
        entities = re.findall(r"\(([^:)]+)(?::[^)]+)?\)", fact_str)
        if not entities:
            # Clean plain entity quotes or words
            entities = [w for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", fact_str) if w.lower() not in {"graph", "uses", "cites", "extends", "true", "false"}]

        if fact_str.lower() in output_lower:
            matched_count += 1
        elif entities and any(e.lower() in output_lower for e in entities):
            matched_count += 1

    return min(1.0, max(0.0, round(matched_count / total_facts, 4)))


def compute_entity_relation_coverage_sets(
    extracted_entities: Optional[Sequence[str]] = None,
    gold_entities: Optional[Sequence[str]] = None,
    extracted_relations: Optional[Sequence[Any]] = None,
    gold_relations: Optional[Sequence[Any]] = None,
) -> float:
    """Computes entity and relation extraction coverage from explicit sets."""
    scores: list[float] = []

    if gold_entities is not None and len(gold_entities) > 0:
        gold_set = {str(e).strip().lower() for e in gold_entities}
        ext_set = {str(e).strip().lower() for e in (extracted_entities or [])}
        ent_recall = len(gold_set & ext_set) / len(gold_set)
        scores.append(ent_recall)

    if gold_relations is not None and len(gold_relations) > 0:
        def _norm_rel(r: Any) -> str:
            if isinstance(r, (list, tuple)):
                return "->".join(str(x).strip().lower() for x in r)
            return str(r).strip().lower()

        gold_rel_set = {_norm_rel(r) for r in gold_relations}
        ext_rel_set = {_norm_rel(r) for r in (extracted_relations or [])}
        rel_recall = len(gold_rel_set & ext_rel_set) / len(gold_rel_set)
        scores.append(rel_recall)

    if not scores:
        return 0.0

    return min(1.0, max(0.0, round(sum(scores) / len(scores), 4)))


class GraphEvaluator(BaseEvaluator):
    """Evaluator for GraphRAG-specific dimensions:

    1. Layer 1 (Indexing):
       - `entity_relation_coverage`: extraction fidelity of nodes and relations
       - `community_coherence`: coherence of clustered community summaries
    2. Layer 2 (Search):
       - `graph_utilization_rate`: ratio of retrieved graph facts utilized in response
    3. Layer 3 (Generation):
       - `global_diversity`: thematic diversity and non-repetition on global queries
    """

    ALL_METRICS = (
        "graph_utilization_rate",
        "community_coherence",
        "global_diversity",
        "entity_relation_coverage",
    )

    METRIC_DESCRIPTIONS = {
        "graph_utilization_rate": (
            "Fraction of retrieved graph facts/subgraph edges actually utilized "
            "or cited in the generated answer (0.0 - 1.0)."
        ),
        "community_coherence": (
            "LLM judge scores 0.0-1.0: does the community summary coherently "
            "and faithfully synthesize its grouped member chunks without hallucination?"
        ),
        "global_diversity": (
            "Measures lexical non-repetition and thematic breadth (0.0 - 1.0) "
            "across distinct community themes for global/aggregation queries."
        ),
        "entity_relation_coverage": (
            "Measures extraction recall/coverage (0.0 - 1.0) of entities and relations "
            "against gold reference facts or source text."
        ),
    }

    def __init__(
        self,
        judge: Optional[BaseJudgeBackend] = None,
        metrics: Optional[list[str]] = None,
    ) -> None:
        self.judge = judge
        self.metrics = metrics or list(self.ALL_METRICS)

    def evaluate(
        self,
        example_input: str,
        output: str,
        reference: Optional[str],
        context: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> dict[str, float]:
        meta = metadata or {}
        scores: dict[str, float] = {}

        # 1. Graph Utilization Rate
        if "graph_utilization_rate" in self.metrics:
            retrieved = meta.get("graph_facts_retrieved")
            if retrieved is None:
                # Extract any `[graph] ...` lines from context
                retrieved = [
                    c.replace("[graph]", "").strip()
                    for c in (context or [])
                    if c.startswith("[graph]") or "(:Paper" in c or "-[:" in c
                ]
            used = meta.get("graph_facts_used")
            citations = meta.get("citations")
            route = meta.get("route_taken") or meta.get("route")
            if retrieved or route in ("graph", "both"):
                scores["graph_utilization_rate"] = compute_graph_utilization_rate(
                    output=output,
                    graph_facts_retrieved=retrieved,
                    graph_facts_used=used,
                    citations=citations,
                )

        # 2. Global Synthesization Diversity
        if "global_diversity" in self.metrics:
            expected_themes = meta.get("expected_themes") or meta.get("communities")
            lex_div = compute_lexical_diversity(output)
            if expected_themes:
                theme_cov = compute_thematic_coverage(output, expected_themes)
                scores["global_diversity"] = round(0.5 * lex_div + 0.5 * theme_cov, 4)
            else:
                scores["global_diversity"] = lex_div

        # 3. Community Coherence (requires Judge)
        if "community_coherence" in self.metrics:
            summary = meta.get("community_summary") or output
            member_context = meta.get("community_chunks") or meta.get("grouped_facts")
            if not member_context and context:
                # Use retrieved chunks or non-summary context
                member_context = [
                    c for c in context if not c.startswith("Community Report")
                ] or context

            member_text = (
                "\n---\n".join(member_context)
                if isinstance(member_context, list)
                else str(member_context or "(no member context)")
            )

            if self.judge is not None:
                prompt = _COMMUNITY_COHERENCE_PROMPT.format(
                    community_context=member_text,
                    summary=summary,
                )
                scores["community_coherence"] = self.judge.score(prompt)
            else:
                scores["community_coherence"] = 0.0

        # 4. Entity & Relation Extraction Coverage
        if "entity_relation_coverage" in self.metrics:
            ext_ent = meta.get("extracted_entities")
            gold_ent = meta.get("gold_entities")
            ext_rel = meta.get("extracted_relations")
            gold_rel = meta.get("gold_relations")

            if gold_ent is not None or gold_rel is not None:
                scores["entity_relation_coverage"] = compute_entity_relation_coverage_sets(
                    extracted_entities=ext_ent,
                    gold_entities=gold_ent,
                    extracted_relations=ext_rel,
                    gold_relations=gold_rel,
                )
            elif reference and self.judge is not None:
                extracted_elements = "\n".join(
                    [c for c in (context or []) if "[graph]" in c]
                ) or output
                prompt = _ENTITY_RELATION_COVERAGE_PROMPT.format(
                    reference=reference,
                    extracted_elements=extracted_elements,
                )
                scores["entity_relation_coverage"] = self.judge.score(prompt)
            else:
                scores["entity_relation_coverage"] = 0.0

        return scores
