"""Tests for language-agnostic prompt assembly."""

from __future__ import annotations

from research.generation.prompt_builder import build_prompt, build_prompt_plain


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
    assert "medium (5–9 words)" in prompt
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
    assert "infinitive" in prompt.lower()


def test_build_prompt_explicit_spanish_overlay():
    from research.generation.prompt_builder import build_prompt_explicit

    prompt = build_prompt_explicit(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=3,
        sentence_length="short",
    )
    assert "Additional requirements:" in prompt
    assert "nosotros" in prompt
    assert "pretérito indefinido" in prompt
    assert 'DO NOT use the infinitive "comer"' in prompt
    assert "expected_form" not in prompt.lower()


def test_inject_expected_form_off_by_default():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=3,
        sentence_length="short",
    )
    assert "Required surface form" not in prompt
    assert "comimos" not in prompt


def test_inject_expected_form_when_provided():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=3,
        sentence_length="short",
        inject_expected_form="comimos",
    )
    assert "Required surface form" in prompt
    assert '"comimos"' in prompt


def test_inject_expected_form_byte_identical_when_none():
    """Sanity: with the parameter absent the prompt is unchanged from baseline."""
    common_kwargs = dict(
        keyword="vivir",
        translation="to live",
        target_language="es",
        constraints={"tense": "future", "person": "3rd", "number": "singular"},
        num_candidates=10,
        sentence_length="short",
        cefr_level="A1",
    )
    p_default = build_prompt(**common_kwargs)
    p_explicit_none = build_prompt(**common_kwargs, inject_expected_form=None)
    assert p_default == p_explicit_none


def test_participle_baseline_prompt_does_not_leak_gold_form():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "participle"},
        num_candidates=10,
        sentence_length="short",
    )
    assert "past participle" in prompt.lower()
    assert "Required surface form" not in prompt
    assert "comido" not in prompt
    assert "Person:" not in prompt


def test_participle_injected_prompt_includes_gold_form():
    prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "participle"},
        num_candidates=10,
        sentence_length="short",
        inject_expected_form="comido",
    )
    assert "Required surface form" in prompt
    assert '"comido"' in prompt


def test_participle_explicit_overlay_without_subject_hints():
    from research.generation.prompt_builder import build_prompt_explicit

    prompt = build_prompt_explicit(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "participle"},
        num_candidates=10,
        sentence_length="short",
        inject_expected_form="comido",
    )
    assert "Additional requirements:" in prompt
    assert "participio pasado" in prompt
    assert "nosotros" not in prompt
    assert "Required surface form" in prompt
    assert '"comido"' in prompt


def test_build_prompt_plain_matches_json_constraints():
    json_prompt = build_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=1,
        sentence_length="short",
        inject_expected_form="comimos",
    )
    plain_prompt = build_prompt_plain(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={"tense": "preterite", "person": "1st", "number": "plural"},
        num_candidates=1,
        sentence_length="short",
        inject_expected_form="comimos",
    )
    for snippet in (
        "Preterite (pretérito indefinido)",
        "Person: 1st",
        "Required surface form",
        '"comimos"',
        "short (2–5 words)",
    ):
        assert snippet in json_prompt
        assert snippet in plain_prompt
    assert "Reply ONLY as JSON" in json_prompt
    assert "No JSON" in plain_prompt


def test_build_prompt_plain_morphology_hints_matches_4a_overlay():
    prompt = build_prompt_plain(
        keyword="buscar",
        translation="to search",
        target_language="es",
        constraints={"tense": "present", "person": "2nd", "number": "plural"},
        num_candidates=1,
        sentence_length="short",
        require_full_sentence=True,
        morphology_hints=True,
    )
    assert "2–5 words" in prompt
    assert "Do NOT output the target form on its own" in prompt
    assert "Additional requirements:" in prompt
    assert "vosotros/vosotras" in prompt
    assert "presente de indicativo" in prompt
    assert "buscáis" not in prompt
    assert "No JSON" in prompt


def test_build_prompt_plain_welsh_peri_uses_expanded_word_band():
    prompt = build_prompt_plain(
        keyword="rhoi",
        translation="give",
        target_language="cy",
        constraints={
            "tense": "present",
            "person": "1st",
            "number": "singular",
            "construction": "periphrastic",
            "expected_aux": "rwyf",
            "particle": "yn",
        },
        num_candidates=1,
        sentence_length="short_expanded",
        require_full_sentence=True,
    )
    assert "short_expanded (4–8 words)" in prompt
    assert "4–8 words" in prompt
    assert "2–5 words" not in prompt


def test_build_prompt_plain_welsh_synthetic_keeps_short_word_band():
    prompt = build_prompt_plain(
        keyword="rhoi",
        translation="give",
        target_language="cy",
        constraints={
            "tense": "past",
            "person": "1st",
            "number": "singular",
            "construction": "synthetic",
        },
        num_candidates=1,
        sentence_length="short",
        require_full_sentence=True,
        inject_expected_form="rhoddais",
    )
    assert "short (2–5 words)" in prompt
    assert "2–5 words" in prompt
    assert "4–8 words" not in prompt
