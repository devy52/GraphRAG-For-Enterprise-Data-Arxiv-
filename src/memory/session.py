"""
Conversational Session Memory & Sliding-Window Buffer Module.

Architecture Role:
    Part of Phase 5 (Question Router & Session Memory). Maintains conversational context
    across multi-turn user dialogues. Enforces a strict sliding-window buffer ($k=3$ turns)
    to balance contextual memory against token budgets, and resolves pronoun coreferences
    ("it", "this paper", "that method") using previously resolved entity mentions before
    query routing and retrieval.

Inputs:
    - User query strings across turns.
    - System responses and extracted entity mentions.

Outputs:
    - Rewritten, self-contained questions with resolved entity coreferences.
    - Sliding-window history of past $k$ turns.

Design Decisions:
    - Window Size Bound (k=3): Restricts memory to the last 3 interaction pairs (6 turns),
      preventing context drift and memory bloat.
    - Rule-Based & Pattern Coreference: Resolves third-person pronouns and demonstratives
      deterministically against the most recent salient entity when offline or before LLM calls.
"""

from datetime import datetime, timezone
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.core.logging import setup_logger
from src.graph.models import EntityType

logger = setup_logger(name="memory.session")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
DEFAULT_WINDOW_SIZE = 3  # Maximum number of query-response turn pairs to retain


class SessionTurn(BaseModel):
    """
    Represents a single conversational turn in a dialogue session.
    """
    turn_id: int = Field(..., description="Monotonically increasing turn index")
    role: str = Field(..., description="'user' or 'assistant'")
    text: str = Field(..., description="Message text content")
    mentioned_entities: List[str] = Field(
        default_factory=list,
        description="Canonical entities identified in this turn",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Turn creation timestamp",
    )


class SessionMemory:
    """
    Manages sliding-window conversational memory and pronoun coreference resolution.
    """

    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE) -> None:
        self.window_size = window_size
        self.turns: List[SessionTurn] = []
        self._turn_counter = 0

    def add_user_turn(self, text: str, entities: Optional[List[str]] = None) -> SessionTurn:
        """
        Records a user query turn into session memory, enforcing sliding window bounds.
        """
        # Step 1: Increment turn sequence counter
        self._turn_counter += 1

        # Step 2: Create structured SessionTurn instance
        turn = SessionTurn(
            turn_id=self._turn_counter,
            role="user",
            text=text.strip(),
            mentioned_entities=entities or [],
        )
        self.turns.append(turn)

        # Step 3: Evict older turns outside the sliding window (retaining 2 * window_size messages)
        max_turns = self.window_size * 2
        if len(self.turns) > max_turns:
            self.turns = self.turns[-max_turns:]

        return turn

    def add_assistant_turn(self, text: str, entities: Optional[List[str]] = None) -> SessionTurn:
        """
        Records an assistant response turn into session memory, enforcing sliding window bounds.
        """
        # Step 1: Increment turn counter
        self._turn_counter += 1

        # Step 2: Create structured SessionTurn instance
        turn = SessionTurn(
            turn_id=self._turn_counter,
            role="assistant",
            text=text.strip(),
            mentioned_entities=entities or [],
        )
        self.turns.append(turn)

        # Step 3: Evict older turns outside sliding window
        max_turns = self.window_size * 2
        if len(self.turns) > max_turns:
            self.turns = self.turns[-max_turns:]

        return turn

    def get_most_recent_entity(self) -> Optional[str]:
        """
        Scans backwards through session history to retrieve the most recently mentioned entity.
        """
        # Step 1: Walk backwards through conversational turns
        for turn in reversed(self.turns):
            if turn.mentioned_entities:
                # Return the last entity mentioned in that turn
                return turn.mentioned_entities[-1]
        return None

    def resolve_coreference(self, query: str) -> str:
        """
        Resolves ambiguous pronouns and demonstrative phrases into explicit entity names.

        Substitutions:
        - "what datasets did it use?" -> "what datasets did <Entity> use?"
        - "who wrote that paper?" -> "who wrote <Entity>?"
        - "what models extend this method?" -> "what models extend <Entity>?"
        """
        # Step 1: Find the latest salient entity from recent dialogue turns
        recent_entity = self.get_most_recent_entity()
        if not recent_entity:
            return query

        resolved_query = query

        # Step 2: Define ambiguous reference patterns
        patterns = [
            (r"\b(it|its)\b", recent_entity),
            (r"\b(that paper|this paper|the paper)\b", f"'{recent_entity}'"),
            (r"\b(that method|this method|the method|that model|this model)\b", f"'{recent_entity}'"),
            (r"\b(that author|the author)\b", f"'{recent_entity}'"),
        ]

        # Step 3: Apply regex replacement on first matching ambiguous reference
        for pattern, replacement in patterns:
            if re.search(pattern, resolved_query, flags=re.IGNORECASE):
                resolved_query = re.sub(pattern, replacement, resolved_query, count=1, flags=re.IGNORECASE)
                logger.debug("Resolved coreference: '%s' -> '%s'", query, resolved_query)
                break

        return resolved_query

    def clear(self) -> None:
        """Clears all turns from session memory."""
        self.turns.clear()
        self._turn_counter = 0
