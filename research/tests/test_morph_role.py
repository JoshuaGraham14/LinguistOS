from __future__ import annotations

import pytest

from research.generation.morph_role import expected_form_is_main_verb


@pytest.fixture(scope="module")
def spacy_es():
    spacy = pytest.importorskip("spacy")
    try:
        return spacy.load("es_core_news_sm")
    except OSError:
        pytest.skip("es_core_news_sm not installed")


def test_expected_form_is_main_verb_accepts_root(spacy_es):
    assert expected_form_is_main_verb("Tú buscas un libro.", "buscas")


def test_expected_form_is_main_verb_rejects_non_root_mention(spacy_es):
    assert not expected_form_is_main_verb(
        "Ella dijo la palabra buscas.",
        "buscas",
    )
