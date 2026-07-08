"""Language-agnostic prompt assembly from constraint profiles."""

from __future__ import annotations

from typing import Any

from research.evaluation.length_bands import band_label
from research.generation.languages import load_language_profile

LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "he": "Hebrew",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ar": "Arabic",
}

# CEFR fluency labels and grammar guidance injected into generation prompts.
CEFR_FLUENCY: dict[str, str] = {
    "A1": "beginner",
    "A2": "elementary",
    "B1": "intermediate",
    "B2": "upper-intermediate",
    "C1": "advanced",
    "C2": "mastery",
}

CEFR_GRAMMAR_GUIDANCE: dict[str, str] = {
    "A1": (
        "Use only short, simple sentences (subject–verb–object). "
        "Avoid subordinate clauses (e.g. que, porque, cuando, si), passive voice, "
        "and any grammar above beginner level."
    ),
    "A2": (
        "Use simple connected sentences with basic conjunctions on familiar topics. "
        "Avoid complex subordination and advanced constructions."
    ),
    "B1": (
        "Use straightforward connected language; subordinate clauses are allowed "
        "but keep them simple."
    ),
    "B2": (
        "Use clear, varied structures appropriate for upper-intermediate learners."
    ),
    "C1": "Use flexible, precise language including complex structures when natural.",
    "C2": "Use nuanced, native-like language at full complexity when natural.",
}


def language_display_name(code: str) -> str:
    try:
        return load_language_profile(code).name
    except ValueError:
        return LANGUAGE_NAMES.get(code, code)


def _explicit_subject_line(
    constraints: dict[str, Any],
    *,
    explicit_subject_required: bool,
) -> str:
    if not explicit_subject_required:
        return ""
    person = constraints.get("person", "")
    number = constraints.get("number", "")
    gender = constraints.get("gender")
    line = (
        f"Include an explicit subject (pronoun or noun phrase) that matches "
        f"person={person}, number={number}"
    )
    if gender:
        line += f", gender={gender}"
    return line + ".\n"


def _cefr_line(cefr_level: str) -> str:
    level = cefr_level.strip().upper()
    fluency = CEFR_FLUENCY.get(level, "learner")
    grammar = CEFR_GRAMMAR_GUIDANCE.get(
        level,
        "Use vocabulary and grammar appropriate for this level.",
    )
    return (
        f"Target learner level: CEFR {level} ({fluency}). "
        f"Vocabulary and grammar must be appropriate for this fluency level. "
        f"{grammar}\n"
    )


def _inflection_line(keyword: str, constraints: dict[str, Any]) -> str:
    if str(constraints.get("tense", "")) == "participle":
        return (
            f'The sentence must contain the past participle of "{keyword}" '
            "— not the bare infinitive.\n"
        )
    parts: list[str] = []
    for key in ("tense", "mood", "person", "number"):
        if key in constraints:
            parts.append(f"{key}={constraints[key]}")
    spec = ", ".join(parts) if parts else "the constraints above"
    return (
        f'The target verb "{keyword}" must appear in the sentence inflected to match '
        f"{spec} — not as the bare infinitive unless the constraints require it.\n"
    )


def _form_injection_line(keyword: str, expected_form: str) -> str:
    """Tell the model the exact gold surface form to bind in each sentence."""
    return (
        f'Required surface form: the verb "{keyword}" must appear in each sentence '
        f'exactly as "{expected_form}" — use this conjugated surface form verbatim '
        "(one token, no infinitive, no other conjugation).\n"
    )


def _constraint_lines(language: str, constraints: dict[str, Any]) -> list[str]:
    profile = load_language_profile(language)
    lines: list[str] = []
    for field in profile.dimension_fields():
        if field not in constraints:
            continue
        value = constraints[field]
        label = profile.label_for(field)
        display = profile.gloss_for(field, str(value))
        lines.append(f"  {label}: {display}")
    return lines


def build_prompt(
    *,
    keyword: str,
    translation: str,
    target_language: str,
    constraints: dict[str, Any],
    num_candidates: int,
    sentence_length: str = "short",
    cefr_level: str | None = None,
    explicit_subject_required: bool = False,
    exercise_type: str | None = None,
    inject_expected_form: str | None = None,
) -> str:
    """Build a generation prompt from a language profile and constraint values.

    When ``inject_expected_form`` is provided, an extra line is appended that
    tells the model the exact gold surface form to bind in every sentence. When
    it is ``None`` (the default), the prompt body is byte-identical to the
    previous behaviour so existing baselines remain reproducible.
    """
    lang = language_display_name(target_language)
    length_desc = band_label(sentence_length)

    constraint_block = "\n".join(_constraint_lines(target_language, constraints))
    if constraint_block:
        constraint_block = f"Constraints:\n{constraint_block}\n  length: {length_desc}.\n"
    else:
        constraint_block = f"Constraints: length={length_desc}.\n"

    cefr_line = _cefr_line(cefr_level) if cefr_level else ""
    inflection_line = _inflection_line(keyword, constraints)

    subject_line = _explicit_subject_line(
        constraints, explicit_subject_required=explicit_subject_required
    )

    exercise_line = ""
    if exercise_type:
        exercise_line = f"Exercise type: {exercise_type}.\n"

    form_line = (
        _form_injection_line(keyword, inject_expected_form)
        if inject_expected_form
        else ""
    )

    return (
        f"You generate {lang} example sentences for vocabulary practice.\n"
        f'Target word (lemma): "{keyword}" (English: "{translation}")\n'
        f"{constraint_block}"
        f"{inflection_line}"
        f"{exercise_line}"
        f"{subject_line}"
        f"{cefr_line}"
        f"{form_line}"
        f"Produce {num_candidates} natural {lang} sentences within the length band. "
        f"Each sentence must contain the target verb inflected as specified above, "
        "with its English translation.\n"
        "Reply ONLY as JSON in this exact shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


_SPANISH_SUBJECT_HINTS: dict[tuple[str, str], str] = {
    ("1st", "singular"): "yo",
    ("2nd", "singular"): "tú",
    ("3rd", "singular"): "él/ella",
    ("1st", "plural"): "nosotros/nosotras",
    ("2nd", "plural"): "vosotros/vosotras",
    ("3rd", "plural"): "ellos/ellas",
}

_SPANISH_TENSE_HINTS: dict[str, str] = {
    "present": "presente de indicativo",
    "preterite": "pretérito indefinido",
    "imperfect": "pretérito imperfecto de indicativo",
    "future": "futuro simple",
    "conditional": "condicional simple",
}


def _spanish_explicit_overlay(
    keyword: str,
    constraints: dict[str, Any],
    *,
    sentence_length: str,
) -> str:
    """Extra Spanish morphology instructions (no gold form)."""
    person = constraints.get("person", "")
    number = constraints.get("number", "")
    tense = constraints.get("tense", "")
    lines: list[str] = []

    lo, hi = None, None
    try:
        from research.evaluation.length_bands import get_band

        lo, hi = get_band(sentence_length)
    except ValueError:
        pass
    if lo is not None and hi is not None:
        lines.append(f"- Length: {lo}–{hi} words per sentence.")

    if str(tense) == "participle":
        lines.append(
            f'- DO NOT use the infinitive "{keyword}" — use the past participle '
            "(participio pasado) as one token."
        )
        lines.append(
            "- The participle must appear as one token in the sentence — "
            "not the bare infinitive."
        )
        return "Additional requirements:\n" + "\n".join(lines) + "\n"

    subject = _SPANISH_SUBJECT_HINTS.get((person, number))
    if subject:
        lines.append(
            f"- Subject: use {subject} or a matching noun phrase "
            f"({person} person, {number})."
        )
    if tense:
        tense_label = _SPANISH_TENSE_HINTS.get(tense, tense)
        lines.append(f"- Verb tense/mood: {tense_label}.")
    if constraints.get("mood"):
        lines.append(f"- Mood: {constraints['mood']}.")

    lines.append(
        f'- DO NOT use the infinitive "{keyword}" — output a conjugated single-word verb form.'
    )
    lines.append(
        "- The conjugated verb must appear as one token in the sentence matching "
        "person, number, tense, and mood above."
    )
    return "Additional requirements:\n" + "\n".join(lines) + "\n"


def build_prompt_explicit(
    *,
    keyword: str,
    translation: str,
    target_language: str,
    constraints: dict[str, Any],
    num_candidates: int,
    sentence_length: str = "short",
    cefr_level: str | None = None,
    explicit_subject_required: bool = False,
    exercise_type: str | None = None,
    inject_expected_form: str | None = None,
) -> str:
    """Stronger prompt for morphology binding.

    By default this does **not** leak ``expected_form``. When
    ``inject_expected_form`` is provided, the gold surface form is appended via
    the same opt-in line used by :func:`build_prompt`; this is the
    form-injection ablation condition.
    """
    base = build_prompt(
        keyword=keyword,
        translation=translation,
        target_language=target_language,
        constraints=constraints,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=cefr_level,
        explicit_subject_required=explicit_subject_required,
        exercise_type=exercise_type,
        inject_expected_form=inject_expected_form,
    )
    if target_language != "es":
        return base
    return base + "\n" + _spanish_explicit_overlay(
        keyword, constraints, sentence_length=sentence_length
    )
