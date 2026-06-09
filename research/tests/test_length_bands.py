"""Tests for sentence length band constants."""

from __future__ import annotations

import pytest

from research.evaluation.length_bands import (
    band_label,
    get_band,
    token_count_in_band,
)


def test_get_band_short():
    assert get_band("short") == (2, 5)


def test_get_band_medium():
    assert get_band("medium") == (5, 9)


def test_get_band_long():
    assert get_band("long") == (10, 16)


def test_get_band_unknown_raises():
    with pytest.raises(ValueError, match="Unknown sentence_length"):
        get_band("tiny")


def test_band_label_includes_numeric_range():
    assert band_label("short") == "short (2–5 tokens)"


def test_token_count_in_band_boundary_five():
    assert token_count_in_band(5, "short") is True
    assert token_count_in_band(5, "medium") is True
    assert token_count_in_band(5, "long") is False
