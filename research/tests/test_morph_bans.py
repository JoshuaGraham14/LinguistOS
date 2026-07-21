from __future__ import annotations

import pytest

from research.generation import morph_bans
from research.generation.morph_bans import (
    MorphBanSet,
    banned_surfaces_in_text,
    build_morph_ban_set,
    encode_bad_words,
)


@pytest.fixture
def buscar_present(monkeypatch):
    monkeypatch.setattr(
        morph_bans,
        "_paradigm_forms",
        lambda lemma, tense: (
            "busco",
            "buscas",
            "busca",
            "buscamos",
            "buscáis",
            "buscan",
        ),
    )
    monkeypatch.setattr(
        morph_bans,
        "_actual_es_form",
        lambda lemma, tense, person, number: "buscas",
    )


def test_full_bans_competitors_infinitive_and_wrong_pronouns(buscar_present):
    ban_set = build_morph_ban_set(
        "buscar", "present", "2nd", "singular", "buscas"
    )

    assert ban_set.mode == "full"
    assert "buscas" not in ban_set.surfaces
    assert {"busco", "busca", "buscamos", "buscáis", "buscan", "buscar"} <= (
        ban_set.competing_forms
    )
    assert "tú" not in ban_set.pronouns
    assert "tu" not in ban_set.pronouns
    assert {"yo", "él", "ella", "nosotros", "vosotros", "ellos"} <= (
        ban_set.pronouns
    )
    assert "el" not in ban_set.pronouns


def test_forms_only_and_pronouns_only_are_true_component_ablations(
    buscar_present,
):
    forms = build_morph_ban_set(
        "buscar",
        "present",
        "2nd",
        "singular",
        "buscas",
        mode="forms_only",
    )
    pronouns = build_morph_ban_set(
        "buscar",
        "present",
        "2nd",
        "singular",
        "buscas",
        mode="pronouns_only",
    )

    assert forms.competing_forms
    assert not forms.pronouns
    assert not pronouns.competing_forms
    assert pronouns.pronouns


def test_shared_gold_form_is_never_banned(monkeypatch):
    monkeypatch.setattr(
        morph_bans,
        "_paradigm_forms",
        lambda lemma, tense: ("buscaba", "buscabas", "buscábamos"),
    )
    monkeypatch.setattr(
        morph_bans,
        "_actual_es_form",
        lambda lemma, tense, person, number: "buscaba",
    )

    ban_set = build_morph_ban_set(
        "buscar", "imperfect", "1st", "singular", "buscaba"
    )
    assert "buscaba" not in ban_set.surfaces


def test_benchmark_gold_wins_over_dictionary_disagreement(
    monkeypatch,
):
    monkeypatch.setattr(
        morph_bans,
        "_paradigm_forms",
        lambda lemma, tense: ("incorrecta", "correcta"),
    )
    monkeypatch.setattr(
        morph_bans,
        "_actual_es_form",
        lambda lemma, tense, person, number: "incorrecta",
    )

    with pytest.warns(RuntimeWarning, match="trusting benchmark"):
        ban_set = build_morph_ban_set(
            "probar", "present", "1st", "singular", "correcta"
        )
    assert "correcta" not in ban_set.surfaces
    assert "incorrecta" in ban_set.surfaces


def test_participle_bans_finite_forms_but_not_gold(monkeypatch):
    monkeypatch.setattr(
        morph_bans,
        "_paradigm_forms",
        lambda lemma, tense: (f"{tense}_finite",),
    )
    ban_set = build_morph_ban_set(
        "buscar", "participle", "", "", "buscado"
    )

    assert "buscado" not in ban_set.surfaces
    assert "buscar" in ban_set.surfaces
    assert len(ban_set.competing_forms) == 6  # infinitive + five finite forms
    assert not ban_set.pronouns


def test_thin_bans_only_habitual_competitors_and_wrong_pronouns(monkeypatch):
    def fake_actual(lemma, tense, person, number):
        table = {
            ("1st", "singular"): "busco",
            ("2nd", "singular"): "buscas",
            ("3rd", "singular"): "busca",
        }
        return table.get((person, number))

    monkeypatch.setattr(morph_bans, "_actual_es_form", fake_actual)
    ban_set = build_morph_ban_set(
        "buscar",
        "present",
        "2nd",
        "singular",
        "buscas",
        mode="thin",
        gate_forms_on_subject=True,
    )

    assert ban_set.mode == "thin"
    assert ban_set.competing_forms == frozenset({"busco", "busca"})
    assert "buscar" not in ban_set.surfaces
    assert "buscas" not in ban_set.surfaces
    assert "yo" in ban_set.pronouns
    assert ban_set.gate_forms_on_subject is True
    assert {"tú", "tu"} <= ban_set.allowed_subjects


def test_agree_bans_all_wrong_slots_and_pronouns_not_infinitive(monkeypatch):
    def fake_actual(lemma, tense, person, number):
        table = {
            ("1st", "singular"): "busco",
            ("2nd", "singular"): "buscas",
            ("3rd", "singular"): "busca",
            ("1st", "plural"): "buscamos",
            ("2nd", "plural"): "buscáis",
            ("3rd", "plural"): "buscan",
        }
        return table.get((person, number))

    monkeypatch.setattr(morph_bans, "_actual_es_form", fake_actual)
    ban_set = build_morph_ban_set(
        "buscar",
        "present",
        "1st",
        "singular",
        "busco",
        mode="agree",
    )

    assert ban_set.mode == "agree"
    assert ban_set.competing_forms == frozenset(
        {"buscas", "busca", "buscamos", "buscáis", "buscan"}
    )
    assert "buscar" not in ban_set.surfaces
    assert "busco" not in ban_set.surfaces
    assert "tú" in ban_set.pronouns
    assert "nosotros" in ban_set.pronouns
    assert "yo" not in ban_set.pronouns


class _FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return [ord(char) for char in text]


def test_encode_bad_words_includes_case_and_space_variants():
    ban_set = MorphBanSet(
        mode="full",
        competing_forms=frozenset({"busca"}),
        pronouns=frozenset(),
    )
    encoded = encode_bad_words(_FakeTokenizer(), ban_set)

    assert [ord(char) for char in "busca"] in encoded
    assert [ord(char) for char in " busca"] in encoded
    assert [ord(char) for char in "Busca"] in encoded


def test_banned_hit_uses_whole_words_not_substrings():
    ban_set = MorphBanSet(
        mode="full",
        competing_forms=frozenset({"busca"}),
        pronouns=frozenset({"yo"}),
    )

    assert banned_surfaces_in_text("Ella busca libros.", ban_set) == {"busca"}
    assert not banned_surfaces_in_text("Nosotros buscamos libros.", ban_set)
