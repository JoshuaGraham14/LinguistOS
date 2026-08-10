"""Tests for baseline GPT generator: prompt building, parsing, no-key guard."""

from __future__ import annotations

from research.generation.baseline_gpt import build_prompt, generate, parse_candidates

_ES_PRETERITE_1PL = {"tense": "preterite", "person": "1st", "number": "plural"}
_ES_FUTURE_3SG = {"tense": "future", "person": "3rd", "number": "singular"}
_ES_PRESENT_2SG = {"tense": "present", "person": "2nd", "number": "singular"}


# ── build_prompt ─────────────────────────────────────────────────────────────


def test_prompt_contains_target_language_spanish():
    prompt = build_prompt("comer", "to eat", _ES_PRETERITE_1PL, 3)
    assert "Spanish" in prompt
    assert "comer" in prompt
    assert "to eat" in prompt


def test_prompt_contains_target_language_hebrew():
    prompt = build_prompt(
        "לאכול",
        "to eat",
        {"tense": "past", "person": "1st", "number": "plural"},
        3,
        target_language="he",
    )
    assert "Hebrew" in prompt
    assert "Spanish" not in prompt


def test_prompt_contains_constraints():
    prompt = build_prompt("vivir", "to live", _ES_FUTURE_3SG, 5)
    assert "Tense: Future" in prompt
    assert "Person: 3rd" in prompt
    assert "Number: Singular" in prompt


def test_prompt_requests_correct_candidate_count():
    prompt = build_prompt("hablar", "to speak", _ES_PRESENT_2SG, 7)
    assert "7" in prompt


def test_prompt_without_cefr_omits_cefr_line():
    prompt = build_prompt("comer", "to eat", _ES_PRETERITE_1PL, 3)
    assert "CEFR" not in prompt


def test_prompt_with_cefr_includes_level():
    prompt = build_prompt(
        "comer", "to eat", _ES_PRETERITE_1PL, 3, cefr_level="B1"
    )
    assert "CEFR B1" in prompt
    assert "intermediate" in prompt


def test_prompt_includes_numeric_length_band():
    prompt = build_prompt(
        "comer", "to eat", _ES_PRETERITE_1PL, 3, sentence_length="medium"
    )
    assert "medium (5–9 words)" in prompt
    assert "length band" in prompt


def test_prompt_with_cefr_none_omits_line():
    prompt = build_prompt(
        "comer", "to eat", _ES_PRETERITE_1PL, 3, cefr_level=None
    )
    assert "CEFR" not in prompt


def test_prompt_explicit_subject_hint_generic():
    prompt = build_prompt(
        "vivir",
        "to live",
        _ES_FUTURE_3SG,
        3,
        sentence_length="long",
        explicit_subject_required=True,
    )
    assert "explicit subject" in prompt
    assert "person=3rd, number=singular" in prompt
    assert "él" not in prompt


def test_hebrew_prompt_glosses_past():
    prompt = build_prompt(
        "לשאול",
        "to ask",
        {"tense": "past", "person": "1st", "number": "singular"},
        3,
        target_language="he",
    )
    assert "Past (עבר)" in prompt


# ── parse_candidates ─────────────────────────────────────────────────────────


def test_parse_valid_json():
    raw = '{"candidates":[{"sentence":"Hola.","translation":"Hello."}]}'
    result = parse_candidates(raw)
    assert len(result) == 1
    assert result[0]["sentence"] == "Hola."
    assert result[0]["translation"] == "Hello."


def test_parse_multiple_candidates():
    raw = (
        '{"candidates":['
        '{"sentence":"A.","translation":"A."},'
        '{"sentence":"B.","translation":"B."}'
        "]}"
    )
    result = parse_candidates(raw)
    assert len(result) == 2


def test_parse_skips_items_missing_sentence():
    raw = '{"candidates":[{"translation":"Hello."}]}'
    result = parse_candidates(raw)
    assert result == []


def test_parse_skips_items_missing_translation():
    raw = '{"candidates":[{"sentence":"Hola."}]}'
    result = parse_candidates(raw)
    assert result == []


def test_parse_skips_non_dict_items():
    raw = '{"candidates":["not a dict", 42]}'
    result = parse_candidates(raw)
    assert result == []


def test_parse_empty_candidates_array():
    raw = '{"candidates":[]}'
    result = parse_candidates(raw)
    assert result == []


def test_parse_missing_candidates_key():
    raw = '{"something_else": []}'
    result = parse_candidates(raw)
    assert result == []


def test_parse_strips_whitespace():
    raw = '{"candidates":[{"sentence":"  Hola.  ","translation":"  Hello.  "}]}'
    result = parse_candidates(raw)
    assert result[0]["sentence"] == "Hola."
    assert result[0]["translation"] == "Hello."


# ── generate (no-key guard) ──────────────────────────────────────────────────


def test_generate_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate("comer", "to eat", _ES_PRETERITE_1PL)
    assert result == []
