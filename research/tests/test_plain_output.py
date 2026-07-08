"""Tests for plain-text generation output parsing."""

from __future__ import annotations

from research.generation.plain_output import (
    PLAIN_NO_TRANSLATION,
    candidate_from_plain,
    parse_plain_sentence,
)


def test_parse_plain_sentence_single_line():
    sentence, mode = parse_plain_sentence("Vosotros escribiréis una carta hoy.")
    assert sentence == "Vosotros escribiréis una carta hoy."
    assert mode == "plain"


def test_parse_plain_strips_quotes_and_label():
    sentence, mode = parse_plain_sentence('Spanish: "Comemos pan."')
    assert sentence == "Comemos pan."
    assert mode == "plain"


def test_parse_plain_rejects_json_leak():
    sentence, mode = parse_plain_sentence('{"candidates":[{"sentence":"Hola"}]}')
    assert sentence == ""
    assert mode == "json_leak"


def test_parse_plain_strips_thinking_block():
    raw = "<think>reasoning</think>\nNosotros comimos ayer."
    sentence, mode = parse_plain_sentence(raw)
    assert sentence == "Nosotros comimos ayer."
    assert mode == "plain"


def test_candidate_from_plain_pipeline_shape():
    cand, mode = candidate_from_plain("Ellos comen arroz.")
    assert mode == "plain"
    assert cand == {"sentence": "Ellos comen arroz.", "translation": PLAIN_NO_TRANSLATION}
