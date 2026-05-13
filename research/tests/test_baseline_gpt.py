"""Tests for baseline GPT generator: prompt building, parsing, no-key guard."""

from __future__ import annotations

from research.generation.baseline_gpt import build_prompt, generate, parse_candidates


# ── build_prompt ─────────────────────────────────────────────────────────────


def test_prompt_contains_target_language_spanish():
    prompt = build_prompt("comer", "to eat", "past", "1st", "plural", 3)
    assert "Spanish" in prompt
    assert "comer" in prompt
    assert "to eat" in prompt


def test_prompt_contains_target_language_hebrew():
    prompt = build_prompt(
        "לאכול", "to eat", "past", "1st", "plural", 3, target_language="he"
    )
    assert "Hebrew" in prompt
    assert "Spanish" not in prompt


def test_prompt_contains_constraints():
    prompt = build_prompt("vivir", "to live", "future", "3rd", "singular", 5)
    assert "tense=future" in prompt
    assert "person=3rd" in prompt
    assert "number=singular" in prompt


def test_prompt_requests_correct_candidate_count():
    prompt = build_prompt("hablar", "to speak", "present", "2nd", "singular", 7)
    assert "7" in prompt


def test_prompt_without_cefr_omits_cefr_line():
    prompt = build_prompt("comer", "to eat", "past", "1st", "plural", 3)
    assert "CEFR" not in prompt


def test_prompt_with_cefr_includes_level():
    prompt = build_prompt(
        "comer", "to eat", "past", "1st", "plural", 3, cefr_level="B1"
    )
    assert "CEFR level: B1" in prompt


def test_prompt_with_cefr_none_omits_line():
    prompt = build_prompt(
        "comer", "to eat", "past", "1st", "plural", 3, cefr_level=None
    )
    assert "CEFR" not in prompt


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
    result = generate("comer", "to eat", "past", "1st", "plural")
    assert result == []
