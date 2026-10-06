# -*- coding: utf-8 -*-
"""
Unit tests for shared text normalizer (src/eval/text_norm.py).
"""

import pytest
from src.eval.text_norm import normalize_text


def test_unicode_hyphen_variants():
    """Verify all hyphen variants evaluate identically."""
    ascii_hyphen = "negative-log-likelihood"
    non_breaking = "negative\u2011log\u2011likelihood"
    en_dash = "negative\u2013log\u2013likelihood"
    em_dash = "negative\u2014log\u2014likelihood"
    minus_sign = "negative\u2212log\u2212likelihood"
    figure_dash = "negative\u2012log\u2012likelihood"
    horizontal_bar = "negative\u2015log\u2015likelihood"

    expected = "negative-log-likelihood"
    assert normalize_text(ascii_hyphen) == expected
    assert normalize_text(non_breaking) == expected
    assert normalize_text(en_dash) == expected
    assert normalize_text(em_dash) == expected
    assert normalize_text(minus_sign) == expected
    assert normalize_text(figure_dash) == expected
    assert normalize_text(horizontal_bar) == expected

    # Test equivalence across all forms
    variants = [ascii_hyphen, non_breaking, en_dash, em_dash, minus_sign, figure_dash, horizontal_bar]
    normalized_variants = [normalize_text(v) for v in variants]
    assert len(set(normalized_variants)) == 1


def test_apostrophe_normalization():
    """Verify smart quotes and accents normalize to standard apostrophe."""
    smart_right = "it’s a retrieval-augmented model"
    smart_left = "it‘s a retrieval-augmented model"
    backtick = "it`s a retrieval-augmented model"
    standard = "it's a retrieval-augmented model"

    expected = "it's a retrieval-augmented model"
    assert normalize_text(smart_right) == expected
    assert normalize_text(smart_left) == expected
    assert normalize_text(backtick) == expected
    assert normalize_text(standard) == expected


def test_whitespace_and_nfkc():
    """Verify collapsing of repeated whitespace and NFKC normalization."""
    raw = "  Dense   Passage   Retrieval \t\n  (DPR)  "
    assert normalize_text(raw) == "dense passage retrieval (dpr)"


def test_empty_and_none():
    """Verify robust handling of empty and None inputs."""
    assert normalize_text("") == ""
    assert normalize_text(None) == ""
