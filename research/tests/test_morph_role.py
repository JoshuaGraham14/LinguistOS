from __future__ import annotations

from research.generation.morph_role import expected_form_is_main_verb


def test_expected_form_is_main_verb_accepts_subject_verb():
    assert expected_form_is_main_verb("Tú buscas un libro.", "buscas")


def test_expected_form_is_main_verb_accepts_plain_unquoted_use():
    assert expected_form_is_main_verb("Buscas un libro en la librería.", "buscas")


def test_expected_form_is_main_verb_rejects_quoted_only():
    assert not expected_form_is_main_verb('La respuesta es "buscas".', "buscas")


def test_expected_form_is_main_verb_rejects_metalanguage_mention():
    assert not expected_form_is_main_verb(
        "Ella dijo la palabra buscas.",
        "buscas",
    )
    assert not expected_form_is_main_verb(
        "La forma correcta es buscas.",
        "buscas",
    )
