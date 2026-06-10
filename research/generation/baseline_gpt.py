"""Baseline GPT generation -- batched: asks for N candidates in one API call.

Extracted from backend/app/api/generate.py and adapted for research use:
no FastAPI dependencies, no lexicon constraints, takes plain dicts.

The prompt is language-agnostic: the target language is passed in as a
parameter and injected into the prompt template.
"""

from __future__ import annotations

import json
import os
from typing import Any

from research.evaluation.length_bands import band_label
from research.generation.base import BaseGenerator

LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "he": "Hebrew",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ar": "Arabic",
}


def _lang_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


# Example subjects shown in the prompt for each person/number pair.
_SUBJECT_EXAMPLES: dict[tuple[str, str], str] = {
    ("1st", "singular"): '"yo"',
    ("1st", "plural"): '"nosotros", "nosotras", or a group noun phrase',
    ("2nd", "singular"): '"tú" or "usted"',
    ("2nd", "plural"): '"vosotros", "ustedes", or a group noun phrase',
    ("3rd", "singular"): '"él", "ella", or a named noun phrase',
    ("3rd", "plural"): '"ellos", "ellas", or a named noun phrase',
}

# Modern Hebrew has three morphological tenses (not biblical qatal/yiqtol labels).
_HEBREW_TENSE_ALIASES: dict[str, str] = {
    "qatal": "past",
    "past": "past",
    "preterite": "past",
    "present_participle": "present",
    "present": "present",
    "yiqtol": "future",
    "future": "future",
}

# canonical tense -> (English name, Hebrew name, form instruction)
_HEBREW_TENSE_INFO: dict[str, tuple[str, str, str]] = {
    "past": (
        "Past",
        "עבר (avar)",
        "Use a past-tense (perfective) finite verb — NOT present (הווה), future (עתיד), or imperative.",
    ),
    "present": (
        "Present",
        "הווה (hoveh)",
        "Use a present-tense (Benoni/participle) finite verb — NOT past (עבר) or future (עתיד).",
    ),
    "future": (
        "Future",
        "עתיד (atid)",
        "Use a future-tense finite verb — NOT present (הווה) or past (עבר).",
    ),
}

_HEBREW_SUBJECT_EXAMPLES: dict[tuple[str, str, str | None], str] = {
    ("1st", "singular", None): '"אני"',
    ("1st", "singular", "masculine"): '"אני" with a masculine verb (e.g. אני מדבר)',
    ("1st", "singular", "feminine"): '"אני" with a feminine verb (e.g. אני מדברת)',
    ("1st", "plural", None): '"אנחנו"',
    ("2nd", "singular", "masculine"): '"אתה"',
    ("2nd", "singular", "feminine"): '"את"',
    ("2nd", "plural", "masculine"): '"אתם"',
    ("2nd", "plural", "feminine"): '"אתן"',
    ("3rd", "singular", "masculine"): '"הוא" or a masculine noun phrase',
    ("3rd", "singular", "feminine"): '"היא" or a feminine noun phrase',
    ("3rd", "plural", "masculine"): '"הם" or a masculine group noun phrase',
    ("3rd", "plural", "feminine"): '"הן" or a feminine group noun phrase',
}


def resolve_hebrew_tense(tense: str) -> str | None:
    """Map benchmark tense label to canonical past/present/future."""
    return _HEBREW_TENSE_ALIASES.get(tense.strip().lower())


def _hebrew_tense_block(tense: str) -> str:
    """Explain Modern Hebrew's three tenses and the required tense for this item."""
    canonical = resolve_hebrew_tense(tense)
    if canonical is None:
        return (
            f"Required tense label: {tense}.\n"
            "Modern Hebrew uses three morphological tenses: Past (עבר / avar), "
            "Present (הווה / hoveh), and Future (עתיד / atid).\n"
        )

    past_en, past_he, past_inst = _HEBREW_TENSE_INFO["past"]
    pres_en, pres_he, pres_inst = _HEBREW_TENSE_INFO["present"]
    fut_en, fut_he, fut_inst = _HEBREW_TENSE_INFO["future"]
    req_en, req_he, req_inst = _HEBREW_TENSE_INFO[canonical]

    return (
        "Modern Hebrew uses exactly three morphological tenses:\n"
        f"  • {past_en} — {past_he}\n"
        f"  • {pres_en} — {pres_he}\n"
        f"  • {fut_en} — {fut_he}\n"
        f"Required tense for this item: {req_en} — {req_he} "
        f"(benchmark label: {tense}).\n"
        f"{req_inst}\n"
    )


def _hebrew_agreement_block(person: str, number: str, gender: str | None) -> str:
    """Person, number, and gender agreement instructions for Hebrew."""
    lines = [
        f"Required agreement: person={person}, number={number}.",
    ]
    if gender:
        lines.append(
            f"Required gender: {gender} — the verb must use the {gender} form "
            f"(e.g. feminine כותבת / מדברת, masculine כותב / מדבר)."
        )
    elif person in ("2nd", "3rd") and number == "singular":
        lines.append(
            "The verb must agree in gender with its subject; choose a subject and "
            "matching verb form consistently."
        )
    return "\n".join(lines) + "\n"


def _hebrew_subject_hint(
    person: str,
    number: str,
    gender: str | None,
    *,
    explicit_subject_required: bool,
) -> str:
    """Anchor person/number (and gender when known) with an overt Hebrew subject."""
    needs_subject = (
        explicit_subject_required
        or person in ("2nd", "3rd")
        or (person == "1st" and number == "singular" and gender)
    )
    if not needs_subject:
        return ""

    gender_key = gender.lower() if gender else None
    examples = _HEBREW_SUBJECT_EXAMPLES.get((person, number, gender_key))
    if examples is None and gender_key is not None:
        examples = _HEBREW_SUBJECT_EXAMPLES.get((person, number, None))
    if examples is None:
        examples = _HEBREW_SUBJECT_EXAMPLES.get((person, number, None), '"אני"')
    return (
        f"Include an explicit subject matching person={person}, number={number}"
        + (f", gender={gender}" if gender else "")
        + f" before the conjugated verb (e.g. {examples}).\n"
    )


def _hebrew_form_block() -> str:
    """Finite-verb requirement shared across Hebrew items."""
    return (
        "Conjugate the verb from the target root in the required tense and agreement. "
        "Use a finite conjugated verb form — not the bare infinitive alone, not an "
        "imperative unless imperative is explicitly requested, and not a different tense.\n"
    )


def _hebrew_prompt_block(
    tense: str,
    person: str,
    number: str,
    gender: str | None,
    *,
    explicit_subject_required: bool,
) -> str:
    """Hebrew-specific tense and agreement context (Past / Present / Future)."""
    return (
        _hebrew_tense_block(tense)
        + _hebrew_agreement_block(person, number, gender)
        + _hebrew_subject_hint(
            person, number, gender, explicit_subject_required=explicit_subject_required
        )
        + _hebrew_form_block()
    )


def _explicit_subject_hint(
    person: str,
    number: str,
    *,
    target_language: str,
    gender: str | None,
    explicit_subject_required: bool,
) -> str:
    """Extra instruction to anchor person/number with an overt subject."""
    if target_language == "he":
        return _hebrew_subject_hint(
            person, number, gender, explicit_subject_required=explicit_subject_required
        )
    if not explicit_subject_required:
        return ""
    examples = _SUBJECT_EXAMPLES.get((person, number))
    if not examples:
        return ""
    return (
        f"Include an explicit subject matching person={person}, number={number} "
        f"(e.g. {examples}) before the conjugated verb.\n"
    )


def build_prompt(
    keyword: str,
    translation: str,
    tense: str,
    person: str,
    number: str,
    num_candidates: int,
    target_language: str = "es",
    sentence_length: str = "short",
    cefr_level: str | None = None,
    explicit_subject_required: bool = False,
    gender: str | None = None,
) -> str:
    """Build the prompt for unconstrained sentence generation.

    The prompt is parameterised by target_language so the same function
    works for any language without code changes. An optional cefr_level
    (e.g. "A2", "B1") asks the model to target that proficiency band.
    """
    lang = _lang_name(target_language)
    length_desc = band_label(sentence_length)
    cefr_line = ""
    if cefr_level:
        cefr_line = f"Target CEFR level: {cefr_level}. Use vocabulary and grammar appropriate for this level.\n"
    gender_norm = gender.strip().lower() if gender else None
    hebrew_block = ""
    if target_language == "he":
        hebrew_block = _hebrew_prompt_block(
            tense,
            person,
            number,
            gender_norm,
            explicit_subject_required=explicit_subject_required,
        )
    subject_line = _explicit_subject_hint(
        person,
        number,
        target_language=target_language,
        gender=gender_norm,
        explicit_subject_required=explicit_subject_required,
    )
    if target_language == "he":
        # Subject + tense/agreement already covered in hebrew_block for 2nd/3rd.
        subject_line = "" if hebrew_block else subject_line
    gender_line = ""
    if gender_norm and target_language != "he":
        gender_line = f"Required gender: {gender_norm}.\n"
    return (
        f"You generate {lang} example sentences for vocabulary practice.\n"
        f'Target word: "{keyword}" (English: "{translation}")\n'
        f"Constraints: tense={tense}, person={person}, "
        f"number={number}, length={length_desc}.\n"
        f"{gender_line}"
        f"{hebrew_block}"
        f"{subject_line}"
        f"{cefr_line}"
        f"Produce {num_candidates} natural {lang} sentences within the length band "
        "sentences that contain the target word, each with its English "
        "translation.\n"
        "Reply ONLY as JSON in this exact shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


def parse_candidates(raw: str) -> list[dict[str, str]]:
    """Parse the JSON response into a list of {sentence, translation} dicts."""
    data: Any = json.loads(raw)
    items = data.get("candidates", []) if isinstance(data, dict) else []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sentence = str(item.get("sentence", "")).strip()
        translation = str(item.get("translation", "")).strip()
        if sentence and translation:
            out.append({"sentence": sentence, "translation": translation})
    return out


def generate(
    keyword: str,
    translation: str,
    tense: str,
    person: str,
    number: str,
    num_candidates: int = 5,
    *,
    target_language: str = "es",
    cefr_level: str | None = None,
    sentence_length: str = "short",
    explicit_subject_required: bool = False,
    gender: str | None = None,
    model: str = "gpt-5.4-nano",
    temperature: float = 0.7,
    api_key: str | None = None,
) -> list[dict[str, str]]:
    """Call OpenAI and return parsed candidates.

    Returns an empty list if the API key is missing or the call fails.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return []

    from openai import OpenAI

    client = OpenAI(api_key=key)

    lang = _lang_name(target_language)
    prompt = build_prompt(
        keyword=keyword,
        translation=translation,
        tense=tense,
        person=person,
        number=number,
        num_candidates=num_candidates,
        target_language=target_language,
        cefr_level=cefr_level,
        sentence_length=sentence_length,
        explicit_subject_required=explicit_subject_required,
        gender=gender,
    )

    completion = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a helpful {lang} language tutor. "
                    "Always respond with valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    return parse_candidates(raw)


class BaselineGPTGenerator(BaseGenerator):
    """Asks for all N candidates in a single API call."""

    def __init__(self, model: str = "gpt-5.4-nano", temperature: float = 0.7):
        self._model = model
        self._temperature = temperature

    @property
    def name(self) -> str:
        return "baseline_gpt"

    def generate(
        self,
        keyword: str,
        translation: str,
        tense: str,
        person: str,
        number: str,
        num_candidates: int,
        *,
        target_language: str = "es",
        cefr_level: str | None = None,
        sentence_length: str = "short",
        explicit_subject_required: bool = False,
        gender: str | None = None,
    ) -> list[dict[str, str]]:
        return generate(
            keyword=keyword,
            translation=translation,
            tense=tense,
            person=person,
            number=number,
            num_candidates=num_candidates,
            target_language=target_language,
            cefr_level=cefr_level,
            sentence_length=sentence_length,
            explicit_subject_required=explicit_subject_required,
            gender=gender,
            model=self._model,
            temperature=self._temperature,
        )
