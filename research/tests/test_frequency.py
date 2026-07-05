"""Tests for :mod:`research.evaluation.lexicon.frequency`.

Focus areas
-----------
- Lemma frequency exceeds bare surface-form frequency (proving the sum-over-
  inflected-forms path actually does something).
- Tier assignment matches the intent baked into the benchmark YAMLs
  (`spanish_basic` verbs land in 'common'; `spanish_niche` verbs in 'rare').
- Irregularity is tense-specific (the whole point of the confound analysis).
- Fallback path is robust when the conjugator can't produce forms.
"""

from __future__ import annotations

import math

import pytest
from wordfreq import word_frequency

from research.evaluation.lexicon.frequency import (
    is_irregular,
    score_verb,
    tier,
    verb_zipf,
)


def _surface_zipf(verb: str, lang: str) -> float:
    f = word_frequency(verb, lang)
    return 0.0 if f <= 0 else math.log10(f * 1_000_000_000)


def test_common_spanish_verb_scores_higher_than_rare() -> None:
    assert verb_zipf("comer", "es") > verb_zipf("henchir", "es")
    assert verb_zipf("hablar", "es") > verb_zipf("argüir", "es")


def test_lemma_frequency_beats_surface_form_for_spanish() -> None:
    # The sum over inflected forms must strictly exceed the infinitive-only
    # Zipf: this is what makes the lemma path meaningful for Spanish, where
    # 'habla' etc. outweigh 'hablar' in real text.
    assert verb_zipf("hablar", "es") > _surface_zipf("hablar", "es")
    assert verb_zipf("comer", "es") > _surface_zipf("comer", "es")


def test_spanish_basic_verbs_are_common() -> None:
    for v in ("comer", "hablar", "vivir", "escribir", "correr"):
        assert tier(v, "es") == "common", f"expected {v} to be common"


def test_spanish_niche_verbs_are_rare() -> None:
    for v in ("henchir", "argüir", "menguar", "empalagar",
              "blandir", "proferir", "atestiguar"):
        assert tier(v, "es") == "rare", f"expected {v} to be rare"


def test_is_irregular_tense_specific_for_tener() -> None:
    # Present: tengo != teno -> irregular.
    assert is_irregular("tener", "present", "es", "1st", "singular") is True
    # Imperfect: tenia matches the regular -er/-ir imperfect paradigm.
    assert is_irregular("tener", "imperfect", "es", "1st", "singular") is False


def test_is_irregular_regular_verb_present() -> None:
    for pn in (("1st", "singular"), ("2nd", "singular"), ("3rd", "plural")):
        assert is_irregular("hablar", "present", "es", *pn) is False
        assert is_irregular("comer", "present", "es", *pn) is False


def test_is_irregular_english_unsupported() -> None:
    with pytest.raises(NotImplementedError):
        is_irregular("run", "present", "en", "1st", "singular")


def test_verb_zipf_fallback_for_unknown_verb() -> None:
    # A made-up infinitive should not raise; it falls back to the surface
    # frequency (which for gibberish will be 0.0 and hence Zipf 0.0).
    assert verb_zipf("xzqvarrr", "es") == 0.0


def test_score_verb_produces_expected_shape() -> None:
    rec = score_verb("tener", "es",
                     tenses=("present", "preterite", "imperfect"),
                     person="1st", number="singular")
    assert rec["verb"] == "tener"
    assert rec["lang"] == "es"
    assert rec["tier"] == "common"
    assert isinstance(rec["zipf"], float)
    # tener 1s: present (tengo), preterite (tuve) irregular; imperfect (tenia) regular.
    assert "present" in rec["tenses_irregular"]
    assert "preterite" in rec["tenses_irregular"]
    assert "imperfect" not in rec["tenses_irregular"]
