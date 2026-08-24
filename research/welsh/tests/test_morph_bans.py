"""Tests for Welsh thin Eurfa morph bans."""

from __future__ import annotations

from research.generation import GENERATOR_REGISTRY
from research.generation.morph_bans import build_morph_ban_set, normalize_surface
from research.welsh.morph_bans import (
    build_welsh_morph_ban_set,
    welsh_neurologic_positive_form,
)
from research.welsh.neurologic_hf import (
    WelshNeurologicHFThinInjectPlainBGenerator,
    WelshNeurologicHFThinPlainBGenerator,
)


def test_registry_has_welsh_neurologic_generators():
    assert "welsh_neurologic_hf_thin_plain_b" in GENERATOR_REGISTRY
    assert "welsh_neurologic_hf_thin_inject_plain_b" in GENERATOR_REGISTRY
    assert GENERATOR_REGISTRY["welsh_neurologic_hf_thin_plain_b"] is (
        WelshNeurologicHFThinPlainBGenerator
    )
    assert GENERATOR_REGISTRY["welsh_neurologic_hf_thin_inject_plain_b"] is (
        WelshNeurologicHFThinInjectPlainBGenerator
    )


def test_positive_form_synthetic_vs_peri():
    syn = {
        "construction": "synthetic",
        "expected_form": "rhannais",
        "expected_aux": "",
    }
    peri = {
        "construction": "periphrastic",
        "expected_form": "rhannu",
        "expected_aux": "byddaf",
    }
    assert welsh_neurologic_positive_form(syn) == "rhannais"
    assert welsh_neurologic_positive_form(peri) == "byddaf"


def test_synthetic_thin_bans_competitors_not_gold():
    constraints = {
        "construction": "synthetic",
        "tense": "past",
        "person": "1st",
        "number": "singular",
        "expected_form": "rhannais",
    }
    ban = build_welsh_morph_ban_set("rhannu", constraints, mode="thin")
    assert normalize_surface("rhannais") not in ban.surfaces
    # 3sg past competitor should be banned.
    assert normalize_surface("rhannodd") in ban.competing_forms
    # Wrong pronouns banned; fi allowed.
    assert normalize_surface("ti") in ban.pronouns
    assert normalize_surface("nhw") in ban.pronouns
    assert normalize_surface("fi") not in ban.pronouns


def test_periphrastic_thin_bans_aux_competitors_and_keeps_gold():
    constraints = {
        "construction": "periphrastic",
        "tense": "future",
        "person": "1st",
        "number": "singular",
        "expected_form": "rhannu",
        "expected_aux": "byddaf",
        "expected_aux_alts": "bydda",
        "particle": "yn",
    }
    ban = build_welsh_morph_ban_set("rhannu", constraints, mode="thin")
    assert normalize_surface("byddaf") not in ban.surfaces
    assert normalize_surface("bydda") not in ban.surfaces
    assert normalize_surface("rhannu") not in ban.surfaces
    # 3sg future aux competitor.
    assert normalize_surface("bydd") in ban.competing_forms
    # Anti construction-flip: synthetic 3sg present of lemma (future has no
    # full lexical paradigm — present tense competitors when tense=future
    # are not in _LEXICAL_EURFA_TENSE for future). For future peri, only aux
    # thin slots apply for lexical map miss — check pronoun bans still work.
    assert normalize_surface("ti") in ban.pronouns
    assert normalize_surface("fi") not in ban.pronouns


def test_periphrastic_past_bans_synthetic_competitors():
    constraints = {
        "construction": "periphrastic",
        "tense": "past",
        "person": "2nd",
        "number": "singular",
        "expected_form": "rannu",  # soft VN
        "expected_aux": "gwnêst",
        "particle": "",
    }
    ban = build_welsh_morph_ban_set("rhannu", constraints, mode="thin")
    assert normalize_surface("gwnêst") not in ban.surfaces
    assert normalize_surface("rannu") not in ban.surfaces
    # Thin synthetic past competitors (1sg/3sg) for lemma.
    assert normalize_surface("rhannais") in ban.competing_forms
    assert normalize_surface("rhannodd") in ban.competing_forms
    # Allowed pronoun for 2sg not banned.
    assert normalize_surface("ti") not in ban.pronouns
    assert normalize_surface("fi") in ban.pronouns


def test_spanish_morph_ban_builder_still_works():
    """Spanish path untouched — smoke that verbecc thin still builds."""
    ban = build_morph_ban_set(
        "comer",
        "present",
        "1st",
        "singular",
        "como",
        mode="thin",
    )
    assert normalize_surface("como") not in ban.surfaces
    assert ban.mode == "thin"


def test_welsh_generator_uses_welsh_bans():
    gen = WelshNeurologicHFThinPlainBGenerator(model="Qwen/Qwen3-1.7B")
    constraints = {
        "construction": "synthetic",
        "tense": "past",
        "person": "1st",
        "number": "singular",
        "expected_form": "rhannais",
    }
    ban = gen._job_morph_ban_set("rhannu", constraints)
    assert ban is not None
    assert normalize_surface("rhannodd") in ban.competing_forms
    assert gen._job_expected_form(constraints) == "rhannais"
    peri = {
        "construction": "periphrastic",
        "expected_form": "rhannu",
        "expected_aux": "byddaf",
    }
    assert gen._job_expected_form(peri) == "byddaf"
