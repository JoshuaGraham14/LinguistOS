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
) -> str:
    """Build a generation prompt from a language profile and constraint values."""
    lang = language_display_name(target_language)
    length_desc = band_label(sentence_length)

    constraint_block = "\n".join(_constraint_lines(target_language, constraints))
    if constraint_block:
        constraint_block = f"Constraints:\n{constraint_block}\n  length: {length_desc}.\n"
    else:
        constraint_block = f"Constraints: length={length_desc}.\n"

    cefr_line = ""
    if cefr_level:
        cefr_line = (
            f"Target CEFR level: {cefr_level}. "
            "Use vocabulary and grammar appropriate for this level.\n"
        )

    subject_line = _explicit_subject_line(
        constraints, explicit_subject_required=explicit_subject_required
    )

    return (
        f"You generate {lang} example sentences for vocabulary practice.\n"
        f'Target word: "{keyword}" (English: "{translation}")\n'
        f"{constraint_block}"
        f"{subject_line}"
        f"{cefr_line}"
        f"Produce {num_candidates} natural {lang} sentences within the length band "
        "that contain the target word, each with its English translation.\n"
        "Reply ONLY as JSON in this exact shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )
