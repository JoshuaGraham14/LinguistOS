"""Tests for sentence length band constants."""

from __future__ import annotations

import pytest

from research.evaluation.length_bands import (
    RANDOM_LENGTH,
    band_label,
    get_band,
    resolve_length_band,
    token_count_in_band,
)


def test_get_band_short():
    assert get_band("short") == (2, 5)
    assert get_band("short_expanded") == (4, 8)


def test_get_band_medium():
    assert get_band("medium") == (5, 9)


def test_get_band_long():
    assert get_band("long") == (10, 16)


def test_get_band_unknown_raises():
    with pytest.raises(ValueError, match="Unknown sentence_length"):
        get_band("tiny")


def test_band_label_includes_numeric_range():
    assert band_label("short") == "short (2–5 words)"
    assert band_label("short_expanded") == "short_expanded (4–8 words)"


def test_sentence_length_for_construction():
    from research.evaluation.length_bands import sentence_length_for_construction

    assert sentence_length_for_construction("periphrastic") == "short_expanded"
    assert sentence_length_for_construction("synthetic") == "short"
    assert sentence_length_for_construction(None) == "short"


def test_resolve_length_band_by_construction():
    from research.evaluation.length_bands import BY_CONSTRUCTION_LENGTH, resolve_length_band

    assert (
        resolve_length_band(BY_CONSTRUCTION_LENGTH, construction="periphrastic")
        == "short_expanded"
    )
    assert resolve_length_band(BY_CONSTRUCTION_LENGTH, construction="synthetic") == "short"


def test_token_count_in_band_boundary_five():
    assert token_count_in_band(5, "short") is True
    assert token_count_in_band(5, "medium") is True
    assert token_count_in_band(5, "long") is False


def test_resolve_length_band_random_returns_fixed_label():
    import random

    resolved = resolve_length_band(RANDOM_LENGTH, rng=random.Random(1))
    assert resolved in {"short", "medium", "long"}
    get_band(resolved)


def test_resolve_length_band_fixed_passthrough():
    assert resolve_length_band("medium") == "medium"
