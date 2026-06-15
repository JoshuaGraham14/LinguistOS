"""Tests for language-agnostic prompt assembly."""

from __future__ import annotations

from research.generation.prompt_builder import build_prompt


def test_spanish_prompt_lists_constraints():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=3,
        sentence_length="medium",
    )
    assert "Spanish" in prompt
    assert "comer" in prompt
    assert "Preterite (pretérito indefinido)" in prompt
    assert "Person: 1st" in prompt
    assert "medium (5–9 tokens)" in prompt
    assert "Constraints:" in prompt


def test_hebrew_prompt_uses_gloss_not_prose_block():
    prompt = build_prompt(
        keyword="לשאול",
        translation="to ask",
        target_language="he",
        constraints={"tense": "past", "person": "1st", "number": "singular"},
        num_candidates=3,
    )
    assert "Hebrew" in prompt
    assert "Past (עבר)" in prompt
    assert "three morphological tenses" not in prompt
    assert "אתה" not in prompt


def test_hebrew_gender_in_constraint_lines():
    prompt = build_prompt(
        keyword="לדבר",
        translation="to speak",
        target_language="he",
        constraints={
            "tense": "present",
            "person": "1st",
            "number": "singular",
            "gender": "feminine",
        },
        num_candidates=3,
    )
    assert "Gender: Feminine" in prompt


def test_explicit_subject_line_generic_no_examples():
    prompt = build_prompt(
        keyword="vivir",
        translation="to live",
        target_language="es",
        constraints={"tense": "future", "person": "3rd", "number": "singular"},
        num_candidates=3,
        explicit_subject_required=True,
    )
    assert "explicit subject" in prompt
    assert "person=3rd, number=singular" in prompt
    assert "él" not in prompt
    assert "yo" not in prompt


def test_cefr_line():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "present", "person": "1st", "number": "singular"},
        num_candidates=3,
        cefr_level="B1",
    )
    assert "CEFR B1" in prompt
    assert "intermediate" in prompt
    assert "inflected" in prompt


def test_inflection_line():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=3,
    )
    assert 'target verb "comer"' in prompt
    assert "tense=preterite" in prompt
    assert "person=1st" in prompt
    assert "number=plural" in prompt
