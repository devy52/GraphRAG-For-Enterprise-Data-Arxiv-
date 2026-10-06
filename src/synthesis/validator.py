"""
Deterministic Citation Validator Module.

Architecture Role:
    Part of Phase 6 (Synthesis & Strict Citation Validation). Serves as an immutable hard gate
    evaluating synthesized text. Verifies that every factual claim containing a citation token
    resolves strictly to a `source_chunk_id` present in the retrieved context. Automatically
    flags and rejects responses containing hallucinated chunk IDs or ungrounded assertions.

Inputs:
    - Generated answer text containing inline citation markers (e.g., `[chunk_001]`, `[chunk: chunk_002]`).
    - Ground-truth set or list of allowed `source_chunk_id`s from the `RetrievalContext`.

Outputs:
    - `CitationValidationResult` indicating validity (`is_valid`), counted citations,
      identified valid IDs, list of hallucinated IDs, and detailed error diagnostics.

Design Decisions:
    - Zero Hallucination Tolerance: Any citation referencing a chunk ID not in `allowed_chunk_ids`
      causes immediate validation failure, triggering regeneration or rejection.
    - Flexible Citation Regex: Supports multiple bracketed formats (`[chunk_123]`, `[chunk: chunk_123]`,
      `[123]`) while extracting clean, normalized alphanumeric chunk IDs.
    - Grounding Enforcement: Optionally enforces that answers to substantive questions cite at least one
      valid chunk ID rather than producing ungrounded assertions.
"""

import re
from typing import Iterable, List, Optional, Set
from pydantic import BaseModel, Field

from src.core.logging import setup_logger

logger = setup_logger(name="synthesis.validator")

# ==============================================================================
# Configuration & Named Constants
# ==============================================================================
# Matches [chunk_id], [chunk: chunk_id], [chunk:chunk_id], and [doc_id_chunk_id]
CITATION_REGEX = re.compile(r"\[(?:chunk:\s*)?([a-zA-Z0-9_\-\.]+)\]", flags=re.IGNORECASE)


class CitationValidationResult(BaseModel):
    """
    Captures the deterministic outcome of citation provenance verification.
    """
    is_valid: bool = Field(
        ...,
        description="True if all citations resolve to retrieved chunk IDs; False otherwise",
    )
    total_citations_found: int = Field(
        default=0,
        description="Total number of citation tokens found in the answer text",
    )
    valid_citations: List[str] = Field(
        default_factory=list,
        description="List of citation IDs that match retrieved chunk IDs",
    )
    hallucinated_citations: List[str] = Field(
        default_factory=list,
        description="List of citation IDs invented by the generator not in retrieved context",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Diagnostic explanation if validation failed",
    )


class CitationValidator:
    """
    Performs deterministic provenance validation on synthesized text against retrieved chunk IDs.
    """

    def __init__(self, citation_pattern: Optional[re.Pattern] = None) -> None:
        self.pattern = citation_pattern or CITATION_REGEX

    def extract_citations(self, text: str) -> List[str]:
        """
        Extracts all citation identifiers found within bracketed tokens in text.

        Example:
            "DPR outperforms BM25 [chunk_01] and uses contrastive loss [chunk: chunk_02]."
            -> ["chunk_01", "chunk_02"]
        """
        # Step 1: Find all regex matches within the target text
        matches = self.pattern.findall(text)
        # Step 2: Strip surrounding whitespace from captured IDs and filter empty strings and reserved context tags
        reserved_tags = {"retrieved", "graph"}
        extracted = [m.strip() for m in matches if m.strip() and m.strip().lower() not in reserved_tags]
        logger.debug("Extracted %d citation(s) from text: %s", len(extracted), extracted)
        return extracted

    def validate(
        self,
        text: str,
        allowed_chunk_ids: Iterable[str],
        require_at_least_one: bool = True,
    ) -> CitationValidationResult:
        """
        Validates text against an allowed set of retrieved source chunk IDs.

        Args:
            text: Synthesized answer string.
            allowed_chunk_ids: Set or list of valid chunk IDs present in retrieval context.
            require_at_least_one: If True, fails validation if no citations are found.

        Returns:
            CitationValidationResult with validity status and diagnostic metrics.
        """
        # Step 1: Normalize allowed chunk IDs into a fast lookup set
        allowed_set: Set[str] = {cid.strip() for cid in allowed_chunk_ids if cid.strip()}

        # Step 2: Extract all citation tokens present in the text
        extracted_citations = self.extract_citations(text)
        total_found = len(extracted_citations)

        # Step 3: Handle zero-citation case
        if total_found == 0:
            # Check if answer expresses refusal or lack of evidence
            lower_text = text.lower()
            refusal_cues = [
                "insufficient evidence",
                "no sufficient evidence",
                "lacks sufficient evidence",
                "not mentioned",
                "not found in the corpus",
                "cannot answer",
                "no evidence",
                "does not contain",
                "lacks evidence",
            ]
            if any(cue in lower_text for cue in refusal_cues):
                return CitationValidationResult(
                    is_valid=True,
                    total_citations_found=0,
                    valid_citations=[],
                    hallucinated_citations=[],
                )

            if require_at_least_one and allowed_set:
                logger.warning("Citation validation failed: zero citations found in substantive response.")
                return CitationValidationResult(
                    is_valid=False,
                    total_citations_found=0,
                    valid_citations=[],
                    hallucinated_citations=[],
                    error_message="Answer contains substantive claims but cites zero source chunk IDs (zero citations found).",
                )
            # If allowed_set was empty, zero citations is valid
            return CitationValidationResult(
                is_valid=True,
                total_citations_found=0,
                valid_citations=[],
                hallucinated_citations=[],
            )

        # Step 4: Partition extracted citations into valid vs hallucinated
        valid_citations: List[str] = []
        hallucinated_citations: List[str] = []

        for citation in extracted_citations:
            if citation in allowed_set:
                valid_citations.append(citation)
            else:
                hallucinated_citations.append(citation)

        # Step 5: Check for hallucinations
        if hallucinated_citations:
            error_msg = (
                f"Detected {len(hallucinated_citations)} hallucinated citation(s): "
                f"{sorted(list(set(hallucinated_citations)))}. "
                f"Allowed chunk IDs: {sorted(list(allowed_set))}."
            )
            logger.error("Citation validation rejected response: %s", error_msg)
            return CitationValidationResult(
                is_valid=False,
                total_citations_found=total_found,
                valid_citations=valid_citations,
                hallucinated_citations=hallucinated_citations,
                error_message=error_msg,
            )

        # Step 6: All citations successfully verified
        logger.info(
            "Citation validation passed: %d valid citation(s) confirmed against retrieved context.",
            total_found,
        )
        return CitationValidationResult(
            is_valid=True,
            total_citations_found=total_found,
            valid_citations=valid_citations,
            hallucinated_citations=[],
            error_message=None,
        )
