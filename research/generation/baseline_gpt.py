"""Baseline GPT generation -- batched: asks for N candidates in one API call.

Extracted from backend/app/api/generate.py and adapted for research use:
no FastAPI dependencies, no lexicon constraints, takes plain dicts.

Prompt assembly is language-agnostic; per-language constraint schemas live in
``research/languages/{code}.yaml``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from research.generation.base import BaseGenerator
from research.generation.prompt_builder import build_prompt as _build_prompt
from research.generation.prompt_builder import language_display_name


def build_prompt(
    keyword: str,
    translation: str,
    constraints: dict[str, Any],
    num_candidates: int,
    target_language: str = "es",
    sentence_length: str = "short",
    cefr_level: str | None = None,
    explicit_subject_required: bool = False,
    exercise_type: str | None = None,
) -> str:
    """Build the prompt for unconstrained sentence generation."""
    return _build_prompt(
        keyword=keyword,
        translation=translation,
        target_language=target_language,
        constraints=constraints,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=cefr_level,
        explicit_subject_required=explicit_subject_required,
        exercise_type=exercise_type,
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
    constraints: dict[str, Any],
    num_candidates: int = 5,
    *,
    target_language: str = "es",
    cefr_level: str | None = None,
    sentence_length: str = "short",
    explicit_subject_required: bool = False,
    exercise_type: str | None = None,
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
    lang = language_display_name(target_language)
    prompt = build_prompt(
        keyword=keyword,
        translation=translation,
        constraints=constraints,
        num_candidates=num_candidates,
        target_language=target_language,
        cefr_level=cefr_level,
        sentence_length=sentence_length,
        explicit_subject_required=explicit_subject_required,
        exercise_type=exercise_type,
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
        constraints: dict[str, Any],
        num_candidates: int,
        *,
        target_language: str = "es",
        cefr_level: str | None = None,
        sentence_length: str = "short",
        explicit_subject_required: bool = False,
    ) -> list[dict[str, str]]:
        return generate(
            keyword=keyword,
            translation=translation,
            constraints=constraints,
            num_candidates=num_candidates,
            target_language=target_language,
            cefr_level=cefr_level,
            sentence_length=sentence_length,
            explicit_subject_required=explicit_subject_required,
            model=self._model,
            temperature=self._temperature,
        )
