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
) -> str:
    """Build the prompt for unconstrained sentence generation.

    The prompt is parameterised by target_language so the same function
    works for any language without code changes. An optional cefr_level
    (e.g. "A2", "B1") asks the model to target that proficiency band.
    """
    lang = _lang_name(target_language)
    cefr_line = ""
    if cefr_level:
        cefr_line = f"Target CEFR level: {cefr_level}. Use vocabulary and grammar appropriate for this level.\n"
    return (
        f"You generate {lang} example sentences for vocabulary practice.\n"
        f'Target word: "{keyword}" (English: "{translation}")\n'
        f"Constraints: tense={tense}, person={person}, "
        f"number={number}, length={sentence_length}.\n"
        f"{cefr_line}"
        f"Produce {num_candidates} natural, {sentence_length}-length {lang} "
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
            model=self._model,
            temperature=self._temperature,
        )
