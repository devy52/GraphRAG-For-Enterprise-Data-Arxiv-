# -*- coding: utf-8 -*-
"""
Shared Unicode and Lexical Normalization Utility.

Architecture Role:
    Canonical text normalizer for evaluation pipelines. Ensures consistent,
    reproducible string comparisons across all evaluation layers, preventing
    false negative discrepancies caused by character encoding quirks (e.g.
    Unicode non-breaking hyphens, smart apostrophes, variable whitespace).

Inputs:
    - Raw text string (from reference answer, gold facts, or model generation).

Outputs:
    - Normalized text string (NFKC, lowercase, normalized hyphens/apostrophes,
      collapsed whitespace).
"""

from __future__ import annotations

import re
import unicodedata

# Unicode character sets for normalization
# Hyphen variants: HYPHEN (U+2010), NON-BREAKING HYPHEN (U+2011), FIGURE DASH (U+2012),
# EN DASH (U+2013), EM DASH (U+2014), HORIZONTAL BAR (U+2015), MINUS SIGN (U+2212), HYPHEN-MINUS (U+002D)
_HYPHEN_PATTERN = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\-]+")

# Apostrophe/quote variants: LEFT SINGLE QUOTATION (U+2018), RIGHT SINGLE QUOTATION (U+2019),
# GRAVE ACCENT (U+0060), ACUTE ACCENT (U+00B4), APOSTROPHE (U+0027)
_APOSTROPHE_PATTERN = re.compile(r"[\u2018\u2019\u0060\u00B4\']")

# Whitespace collapsing
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str | None) -> str:
    """
    Normalizes a text string for authoritative evaluation comparison.

    Rules applied:
    1. Handle None / non-string gracefully -> return empty string.
    2. Unicode NFKC normalization.
    3. Lowercase.
    4. Normalize all apostrophe/single-quote variants to standard ASCII apostrophe (').
    5. Normalize all hyphen/dash/minus variants to standard ASCII hyphen (-).
    6. Collapse repeated whitespace and strip leading/trailing whitespace.

    Args:
        text: Raw input string.

    Returns:
        Canonical normalized string.
    """
    if not text:
        return ""

    # Step 1: Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", str(text))

    # Step 2: Lowercase
    normalized = normalized.lower()

    # Step 3: Normalize apostrophes
    normalized = _APOSTROPHE_PATTERN.sub("'", normalized)

    # Step 4: Normalize hyphen variants to single standard ASCII hyphen
    normalized = _HYPHEN_PATTERN.sub("-", normalized)

    # Step 5: Collapse repeated whitespace and strip
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized).strip()

    return normalized
