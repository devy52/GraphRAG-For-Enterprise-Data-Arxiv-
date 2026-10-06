"""
Intent-Based Question Router & Classifier Module.

Architecture Role:
    Part of Phase 5 (Question Router & Session Memory). Evaluates user queries to classify
    retrieval intent into `graph`, `vector`, or `both` (hybrid). Enforces a strict
    confidence threshold (0.70): any classification yielding confidence below 0.70 automatically
    escalates to the hybrid (`both`) path to guarantee recall for ambiguous or complex questions.

Inputs:
    - User query string (after coreference resolution from SessionMemory).
    - Optional pre-identified entities from the dialogue turn.

Outputs:
    - `RoutingResult` containing the `RouteDecision` ('graph' | 'vector' | 'both'),
      numerical confidence score, decision reasoning, and matched Cypher template if applicable.

Design Decisions:
    - Tri-State Intent Classification: Relational multi-hop questions route to 'graph', unstructured
      semantic / conceptual questions route to 'vector', and multi-faceted or cross-cutting questions
      route to 'both'.
    - Confidence Escalation Guardrail: If intent confidence is < 0.70, the router defaults to `both`
      to prevent missing crucial context when intent is ambiguous.
    - Dual Engine (LLM Few-Shot + Deterministic Rule Fallback): Uses OpenRouter/NVIDIA LLM when API keys
      are active; employs deterministic lexical, syntactic, and template-matching heuristics when
      offline or testing without external network access.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from openai import AsyncOpenAI

from src.core.config import get_settings
from src.core.logging import setup_logger
from src.graph.query_engine import GraphQueryEngine
from src.graph.templates import CYPHER_TEMPLATES, QueryTemplateType
from src.router.models import RouteDecision, RoutingResult

logger = setup_logger(name="router.classifier")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
MIN_CONFIDENCE_THRESHOLD = 0.70   # Escalation floor: confidence < 0.70 forces RouteDecision.BOTH
HEURISTIC_SKIP_LLM_THRESHOLD = 0.85  # Skip LLM router call when heuristic confidence >= this value
DEFAULT_LLM_TEMPERATURE = 0.0     # Deterministic routing decisions

# Structural / Relational cues strongly indicative of Graph queries
GRAPH_RELATIONAL_PATTERNS = [
    r"\b(who co-authored|co-author|coauthors|co-authorship|collaborators)\b",
    r"\b(papers citing|cited by|citations of|citation network|citation chain)\b",
    r"\b(which papers cite|who wrote|authors of|written by)\b",
    r"\b(datasets used by|what datasets did|evaluate on dataset|evaluated on)\b",
    r"\b(methods extending|extends method|lineage of|derived from)\b",
    r"\b(compare methods used|shared authors|common collaborators)\b",
    r"\b(multi-hop|graph of|connected to)\b",
]

# Unstructured / Semantic cues strongly indicative of Dense Vector queries
VECTOR_SEMANTIC_PATTERNS = [
    r"\b(summarize|summary|overview of|abstract of)\b",
    r"\b(explain the intuition|mathematical intuition|theoretical basis)\b",
    r"\b(how does the|how does this|how is the|what is the concept)\b",
    r"\b(describe the architecture|loss function|chunking strategy)\b",
    r"\b(in section|in paragraph|detailed explanation)\b",
    r"\b(why does|what are the limitations of|discussion on)\b",
]

# Cross-cutting cues indicating multi-faceted queries requiring both Graph + Vector
HYBRID_PATTERNS = [
    r"\b(and explain|and summarize|and describe why)\b",
    r"\b(which methods evaluate on .* and how do they work)\b",
    r"\b(cite .* and explain the difference)\b",
]

ROUTER_SYSTEM_PROMPT = """You are an enterprise query router for a scientific GraphRAG system.
Given a user question, classify the retrieval intent into exactly one of three routes:
- "graph": For structured relational, lineage, co-authorship, citation chains, or dataset-method linkage queries.
- "vector": For semantic explanations, high-level summaries, conceptual discussions, or specific text descriptions.
- "both": For multi-faceted queries combining relational facts with descriptive text, or queries spanning both structures.

Output ONLY valid JSON with this schema:
{
  "route": "graph" | "vector" | "both",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<short explanation>"
}

Examples:
- "What methods extend Dense Passage Retrieval?": {"route": "graph", "confidence": 0.95, "reasoning": "Lineage query asking for methods extending a base model"}
- "Who co-authored papers with Patrick Lewis?": {"route": "graph", "confidence": 0.95, "reasoning": "Relational co-authorship lookup"}
- "Explain the mathematical intuition behind DPR": {"route": "vector", "confidence": 0.95, "reasoning": "Semantic conceptual explanation"}
- "Which methods evaluate on HotpotQA and explain why they achieve higher accuracy?": {"route": "both", "confidence": 0.90, "reasoning": "Combines structured dataset-method evaluation with semantic reasoning"}
- "Tell me something interesting about accuracy.": {"route": "both", "confidence": 0.40, "reasoning": "Ambiguous query without clear intent, escalate to both"}
"""


class RouteClassifier:
    """
    Classifies user queries into graph, vector, or hybrid retrieval routes.
    """

    def __init__(
        self,
        query_engine: Optional[GraphQueryEngine] = None,
        use_llm: bool = True,
        llm_client: Optional[AsyncOpenAI] = None,
    ) -> None:
        self.settings = get_settings()
        self.query_engine = query_engine or GraphQueryEngine()
        self.use_llm = use_llm
        self.llm_client: Optional[AsyncOpenAI] = llm_client

        if not self.use_llm:
            return

        if self.llm_client is None:
            # Initialize LLM client only if a valid, non-placeholder key is supplied
            is_dummy_key = (
                not self.settings.llm_api_key
                or self.settings.llm_api_key.startswith("sk-dummy")
                or self.settings.llm_api_key == "your_api_key_here"
            )
            if not is_dummy_key:
                self.llm_client = AsyncOpenAI(
                    base_url=self.settings.llm_base_url,
                    api_key=self.settings.llm_api_key,
                    timeout=self.settings.request_timeout_seconds,
                )

    def _heuristic_classify(
        self,
        query: str,
        detected_entities: Optional[List[str]] = None,
    ) -> RoutingResult:
        """
        Classifies intent deterministically using regex pattern dominance and template matching.
        Guarantees 100% offline self-sufficiency for tests and fallback execution.
        """
        # Step 1: Detect entities in text via GraphQueryEngine if not already provided
        entities = detected_entities or []
        if not entities:
            found = self.query_engine.identify_entities_in_text(query)
            entities = [name for name, _ in found]

        # Step 2: Attempt matching against parameterized Cypher templates
        best_template: Optional[Tuple[QueryTemplateType, Dict[str, Any]]] = None
        if entities:
            entity_tuples = self.query_engine.identify_entities_in_text(query)
            best_template = self.query_engine.detect_best_template(query, entity_tuples)

        template_id = best_template[0].value if best_template else None

        # Step 3: Count regex pattern hits across categories
        raw_graph_hits = sum(1 for pat in GRAPH_RELATIONAL_PATTERNS if re.search(pat, query, re.IGNORECASE))
        vector_hits = sum(1 for pat in VECTOR_SEMANTIC_PATTERNS if re.search(pat, query, re.IGNORECASE))
        hybrid_hits = sum(1 for pat in HYBRID_PATTERNS if re.search(pat, query, re.IGNORECASE))

        # Boost graph score only if structural pattern matched or if query has an entity with no semantic keywords
        graph_hits = raw_graph_hits
        if raw_graph_hits > 0 and template_id:
            graph_hits += 1
        elif raw_graph_hits == 0 and vector_hits == 0 and template_id:
            graph_hits += 1

        logger.debug(
            "Heuristic scores for '%s': graph=%d (raw=%d), vector=%d, hybrid=%d, template=%s",
            query, graph_hits, raw_graph_hits, vector_hits, hybrid_hits, template_id,
        )

        # Step 4: Decision arbitration and confidence calculation
        if hybrid_hits > 0 or (raw_graph_hits > 0 and vector_hits > 0):
            decision = RouteDecision.BOTH
            confidence = 0.85
            reasoning = "Query contains both relational and semantic cues requiring hybrid retrieval."
        elif graph_hits > vector_hits:
            decision = RouteDecision.GRAPH
            confidence = min(0.95, 0.70 + (graph_hits * 0.10))
            reasoning = f"Matched {graph_hits} structural/relational pattern(s) and Cypher template '{template_id}'."
        elif vector_hits > graph_hits or (vector_hits > 0 and raw_graph_hits == 0):
            decision = RouteDecision.VECTOR
            confidence = min(0.95, 0.70 + (vector_hits * 0.10))
            reasoning = f"Matched {vector_hits} semantic/conceptual pattern(s) best answered via text chunks."
        else:
            # Ambiguous: No strong pattern match -> low confidence falls back to BOTH
            decision = RouteDecision.BOTH
            confidence = 0.50
            reasoning = "Ambiguous query intent; escalated to hybrid ('both') to guarantee recall."

        # Step 5: Enforce confidence escalation guardrail
        if confidence < MIN_CONFIDENCE_THRESHOLD and decision != RouteDecision.BOTH:
            logger.info(
                "Escalating route from '%s' to 'both' due to low confidence (%.2f < %.2f)",
                decision.value, confidence, MIN_CONFIDENCE_THRESHOLD,
            )
            decision = RouteDecision.BOTH
            reasoning += f" (Escalated to 'both': confidence {confidence:.2f} < {MIN_CONFIDENCE_THRESHOLD})"

        return RoutingResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            resolved_query=query,
            detected_entities=entities,
            graph_template_id=template_id,
        )

    async def classify(
        self,
        query: str,
        detected_entities: Optional[List[str]] = None,
    ) -> RoutingResult:
        """
        Classifies the incoming query into a RouteDecision.
        Uses heuristic-first gate: if heuristic confidence >= 0.85, skips the LLM call.
        Otherwise uses OpenAI-compatible gateway if configured; falls back to heuristics.
        """
        # Step 1: Always run heuristic first (fast, <1ms)
        heuristic_result = self._heuristic_classify(query, detected_entities)

        # Step 2: If heuristic is confident enough, skip the expensive LLM call
        if heuristic_result.confidence >= HEURISTIC_SKIP_LLM_THRESHOLD:
            logger.info(
                "Heuristic confidence %.2f >= %.2f; skipping LLM router call (route=%s)",
                heuristic_result.confidence,
                HEURISTIC_SKIP_LLM_THRESHOLD,
                heuristic_result.decision.value,
            )
            return heuristic_result

        # Step 3: Fall back to heuristic if live LLM client is unavailable
        if not self.llm_client:
            return heuristic_result

        # Step 4: Query the LLM classifier with few-shot guidance for ambiguous queries
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.settings.router_model,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {query}"},
                ],
                temperature=DEFAULT_LLM_TEMPERATURE,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_content)

            raw_route = parsed.get("route", "both").lower()
            confidence = float(parsed.get("confidence", 0.5))
            reasoning = parsed.get("reasoning", "LLM-based classification")

            # Validate route string into enum
            if raw_route == "graph":
                decision = RouteDecision.GRAPH
            elif raw_route == "vector":
                decision = RouteDecision.VECTOR
            else:
                decision = RouteDecision.BOTH

            # Step 5: Enforce low confidence escalation (< 0.70 -> BOTH)
            if confidence < MIN_CONFIDENCE_THRESHOLD and decision != RouteDecision.BOTH:
                logger.info(
                    "LLM classified as '%s' with low confidence %.2f; escalating to 'both'",
                    decision.value, confidence,
                )
                decision = RouteDecision.BOTH
                reasoning += f" [Escalated to 'both': confidence {confidence:.2f} < {MIN_CONFIDENCE_THRESHOLD}]"

            # Check for matching graph template if route involves graph
            template_id = None
            if decision in (RouteDecision.GRAPH, RouteDecision.BOTH):
                entity_tuples = self.query_engine.identify_entities_in_text(query)
                best_template = self.query_engine.detect_best_template(query, entity_tuples)
                if best_template:
                    template_id = best_template[0].value

            return RoutingResult(
                decision=decision,
                confidence=confidence,
                reasoning=reasoning,
                resolved_query=query,
                detected_entities=detected_entities or [],
                graph_template_id=template_id,
            )

        except Exception as exc:
            logger.warning("LLM router classification failed (%s); falling back to heuristic", exc)
            return heuristic_result
