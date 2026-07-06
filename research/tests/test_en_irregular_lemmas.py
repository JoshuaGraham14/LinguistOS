"""Tests for programmatic English past-tense irregularity."""

from __future__ import annotations

from research.evaluation.lexicon.en_irregular_lemmas import en_past_tense_irregular
from research.evaluation.lexicon.en_gold_forms import en_past_and_participle


def test_regular_verbs_are_not_irregular() -> None:
    for v in ("walk", "matriculate", "habituate", "flub"):
        assert en_past_tense_irregular(v) is False


def test_suppletive_verbs_are_irregular() -> None:
    for v in ("go", "run", "sing", "befall"):
        assert en_past_tense_irregular(v) is True


def test_prefix_compound_irregular_in_low_tier() -> None:
    assert en_past_tense_irregular("outrun") is True
    assert en_past_tense_irregular("overhear") is True


def test_gold_forms_use_lemminflect_for_table_verbs() -> None:
    past, _ = en_past_and_participle("do")
    assert past[0] == "did"
    past, _ = en_past_and_participle("teach")
    assert past[0] == "taught"


def test_gold_forms_use_lemminflect_for_unknown_census_verbs() -> None:
    past, part = en_past_and_participle("outrun")
    assert "outran" in past
    assert part  # non-empty participle tuple
