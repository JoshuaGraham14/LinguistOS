"""Tests for per-language constraint profiles."""

from __future__ import annotations

import pytest

from research.generation.languages import (
    extract_constraints,
    format_constraint_value,
    load_language_profile,
)


def test_load_hebrew_profile():
    profile = load_language_profile("he")
    assert profile.code == "he"
    assert profile.name == "Hebrew"
    assert "past" in profile.dimensions["tense"]
    assert "binyan" in profile.dimensions


def test_load_spanish_profile():
    profile = load_language_profile("es")
    assert profile.code == "es"
    assert "preterite" in profile.dimensions["tense"]
    assert "participle" in profile.dimensions["tense"]
    assert "binyan" not in profile.dimensions


def test_validate_accepts_spanish_participle_without_person_number():
    profile = load_language_profile("es")
    profile.validate({"tense": "participle"})


def test_validate_rejects_person_on_spanish_participle():
    profile = load_language_profile("es")
    with pytest.raises(ValueError, match="must not include 'person'"):
        profile.validate({"tense": "participle", "person": "1st"})


def test_validate_still_requires_person_for_indicative():
    profile = load_language_profile("es")
    with pytest.raises(ValueError, match="missing required constraint 'person'"):
        profile.validate({"tense": "present", "number": "singular"})


def test_validate_rejects_qatal_for_hebrew():
    profile = load_language_profile("he")
    with pytest.raises(ValueError, match="invalid value 'qatal'"):
        profile.validate({"tense": "qatal", "person": "1st", "number": "singular"})


def test_validate_rejects_binyan_for_spanish():
    profile = load_language_profile("es")
    with pytest.raises(ValueError, match="unknown constraint field 'binyan'"):
        profile.validate({
            "tense": "present",
            "person": "1st",
            "number": "singular",
            "binyan": "piel",
        })


def test_validate_accepts_valid_hebrew():
    profile = load_language_profile("he")
    profile.validate({
        "tense": "past",
        "person": "1st",
        "number": "singular",
        "gender": "feminine",
    })


def test_gloss_for_hebrew_past():
    profile = load_language_profile("he")
    assert profile.gloss_for("tense", "past") == "Past (עבר)"


def test_gloss_fallback_titlecase():
    profile = load_language_profile("es")
    assert profile.gloss_for("tense", "present") == "Present"
    assert format_constraint_value("imperfect_subjunctive") == "Imperfect Subjunctive"


def test_extract_constraints_from_flat_yaml():
    cs = {
        "keyword": "לדבר",
        "expected_form": "מדבר",
        "translation": "to speak",
        "tense": "present",
        "person": "1st",
        "number": "singular",
        "gender": "masculine",
    }
    assert extract_constraints(cs) == {
        "tense": "present",
        "person": "1st",
        "number": "singular",
        "gender": "masculine",
    }


def test_extract_companions_welsh_aux_particle_only():
    from research.generation.languages import extract_companions

    cs = {
        "keyword": "credu",
        "expected_form": "credu",
        "expected_form_alts": "gredu",
        "expected_aux": "rwyf",
        "expected_aux_alts": "dw|rwy",
        "particle": "yn",
        "cell_id": "periphrastic_present_1s",
        "translation": "believe",
        "tense": "present",
        "person": "1st",
        "number": "singular",
        "construction": "periphrastic",
        "tier": "high",
        "zipf": 5.7,
    }
    assert extract_constraints(cs) == {
        "tense": "present",
        "person": "1st",
        "number": "singular",
        "construction": "periphrastic",
    }
    assert extract_companions(cs) == {
        "expected_form_alts": "gredu",
        "expected_aux": "rwyf",
        "expected_aux_alts": "dw|rwy",
        "particle": "yn",
        "cell_id": "periphrastic_present_1s",
    }


def test_extract_companions_spanish_empty():
    from research.generation.languages import extract_companions

    cs = {
        "keyword": "comer",
        "expected_form": "como",
        "translation": "to eat",
        "tense": "present",
        "person": "1st",
        "number": "singular",
    }
    assert extract_companions(cs) == {}
