"""Tests for :mod:`research.evaluation.lexicon.frequency`."""

from __future__ import annotations

import math

import pytest
from wordfreq import word_frequency

from research.evaluation.lexicon.frequency import (
    filter_by_tier,
    in_census,
    is_irregular,
    sample_verbs,
    score_verb,
    tier,
    tier_from_zipf,
    verb_zipf,
    verbs_in_tier,
)


def _surface_zipf(verb: str, lang: str) -> float:
    f = word_frequency(verb, lang)
    return 0.0 if f <= 0 else math.log10(f * 1_000_000_000)


def test_common_spanish_verb_scores_higher_than_obscure() -> None:
    assert verb_zipf("comer", "es") > verb_zipf("henchir", "es")
    assert verb_zipf("hablar", "es") > verb_zipf("argüir", "es")


def test_lemma_frequency_beats_surface_form_for_spanish() -> None:
    assert verb_zipf("hablar", "es") > _surface_zipf("hablar", "es")
    assert verb_zipf("comer", "es") > _surface_zipf("comer", "es")


def test_spanish_basic_verbs_are_high_tier() -> None:
    for v in ("comer", "hablar", "vivir", "escribir", "correr"):
        assert tier(v, "es") == "high", f"expected {v} to be high"


def test_spanish_niche_verbs_are_low_tier() -> None:
    for v in ("henchir", "argüir", "menguar", "empalagar",
              "blandir", "proferir", "atestiguar"):
        assert tier(v, "es") == "low", f"expected {v} to be low"


def test_niche_verbs_not_in_census_but_still_tiered() -> None:
    assert in_census("henchir", "es") is False
    assert tier("henchir", "es") == "low"


def test_census_high_verbs_are_in_census() -> None:
    assert in_census("comer", "es") is True
    assert tier("comer", "es") == "high"


def test_census_partition_covers_all_verbs() -> None:
    high = verbs_in_tier("high", "es")
    mid = verbs_in_tier("mid", "es")
    low = verbs_in_tier("low", "es")
    assert len(high) + len(mid) + len(low) == 1180
    assert len(set(high) & set(mid) & set(low)) == 0


def test_tier_from_zipf_boundaries() -> None:
    low_upper, high_lower = 4.131, 4.693
    assert tier_from_zipf(low_upper - 0.01, "es") == "low"
    assert tier_from_zipf(high_lower, "es") == "high"
    assert tier_from_zipf((low_upper + high_lower) / 2, "es") == "mid"


def test_filter_by_tier_on_candidate_list() -> None:
    candidates = ["comer", "henchir", "hablar", "argüir"]
    assert filter_by_tier(candidates, "high", "es") == ["comer", "hablar"]
    assert filter_by_tier(candidates, "low", "es") == ["henchir", "argüir"]


def test_sample_verbs_respects_exclude() -> None:
    picked = sample_verbs("high", "es", n=3, exclude={"comer", "hablar", "tener"})
    assert len(picked) == 3
    assert "comer" not in picked
    assert all(tier(v, "es") == "high" for v in picked)


def test_is_irregular_tense_specific_for_tener() -> None:
    assert is_irregular("tener", "present", "es", "1st", "singular") is True
    assert is_irregular("tener", "imperfect", "es", "1st", "singular") is False


def test_is_irregular_regular_verb_present() -> None:
    for pn in (("1st", "singular"), ("2nd", "singular"), ("3rd", "plural")):
        assert is_irregular("hablar", "present", "es", *pn) is False
        assert is_irregular("comer", "present", "es", *pn) is False


def test_is_irregular_english_unsupported() -> None:
    with pytest.raises(NotImplementedError):
        is_irregular("run", "present", "en", "1st", "singular")


def test_verb_zipf_fallback_for_unknown_verb() -> None:
    assert verb_zipf("xzqvarrr", "es") == 0.0


def test_score_verb_produces_expected_shape() -> None:
    rec = score_verb("tener", "es",
                     tenses=("present", "preterite", "imperfect"),
                     person="1st", number="singular")
    assert rec["verb"] == "tener"
    assert rec["lang"] == "es"
    assert rec["tier"] == "high"
    assert rec["in_census"] is True
    assert "present" in rec["tenses_irregular"]
    assert "preterite" in rec["tenses_irregular"]
    assert "imperfect" not in rec["tenses_irregular"]
