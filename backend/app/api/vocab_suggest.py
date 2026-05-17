"""Vocabulary suggestion and enrichment endpoints.

The suggestion endpoint is intentionally small and fast: it returns only
direct lexical candidates plus a POS tag. Full vocab metadata is generated
only after the user selects one candidate.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api._auth import ensure_workspace_owner
from app.config import settings
from app.db.database import get_db
from app.db.models import Workspace
from app.db.schemas import LanguageCode, VocabTag

router = APIRouter()

SuggestDirection = Literal["en-to-target", "target-to-en"]

LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "fr": "French",
    "he": "Hebrew",
}

VALID_TAGS: set[str] = {"noun", "verb", "adjective", "adverb", "preposition", "other"}


class VocabSuggestRequest(BaseModel):
    workspace_id: int = Field(ge=1)
    input_text: str = Field(min_length=1, max_length=255)
    direction: SuggestDirection


class VocabSuggestion(BaseModel):
    text: str = Field(min_length=1, max_length=255)
    pos: VocabTag = "other"


class VocabSuggestResponse(BaseModel):
    candidates: list[VocabSuggestion] = Field(default_factory=list)
    mock: bool = False
    field_swap: bool = False
    resolved_direction: SuggestDirection | None = None


class VocabEnrichRequest(BaseModel):
    workspace_id: int = Field(ge=1)
    input_text: str = Field(min_length=1, max_length=255)
    selected_text: str = Field(min_length=1, max_length=255)
    direction: SuggestDirection
    pos: VocabTag = "other"


class VocabDraft(BaseModel):
    surface_form: str
    lemma: str
    gloss_primary: str
    glosses: list[str] = Field(default_factory=list)
    pos: VocabTag = "other"
    tags: list[VocabTag] = Field(default_factory=list)
    cefr: str | None = None
    frequency_rank: int | None = None
    gender: str | None = None
    conjugation_class: str | None = None
    morph_features: dict[str, Any] | None = None
    ipa: str | None = None
    notes: str | None = None


class VocabEnrichResponse(BaseModel):
    draft: VocabDraft
    mock: bool = False


_DEV_LEXICON: dict[tuple[str, SuggestDirection], list[tuple[str, VocabTag]]] = {
    ("to eat", "en-to-target"): [("comer", "verb")],
    ("eat", "en-to-target"): [("comer", "verb")],
    ("to play", "en-to-target"): [("jugar", "verb"), ("tocar", "verb")],
    ("play", "en-to-target"): [("jugar", "verb"), ("tocar", "verb")],
    ("comer", "target-to-en"): [("to eat", "verb")],
    ("jugar", "target-to-en"): [("to play", "verb")],
    ("tocar", "target-to-en"): [("to touch", "verb"), ("to play music", "verb")],
}

# Second-pass mock: input was in the wrong field; keyed by (text, attempted direction).
_DEV_MISPLACED: dict[tuple[str, SuggestDirection], list[tuple[str, VocabTag]]] = {
    ("hello", "target-to-en"): [("hola", "other")],
    ("hola", "en-to-target"): [("hello", "other")],
}


def _language_name(language: LanguageCode) -> str:
    return LANGUAGE_NAMES.get(language, language)


def _workspace_language(db: Session, workspace_id: int) -> LanguageCode:
    ensure_workspace_owner(db, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    # ``ensure_workspace_owner`` already validates existence, but keep a
    # defensive fallback so type narrowing stays simple.
    return (workspace.language if workspace else "es")  # type: ignore[return-value]


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _coerce_tag(value: str | None) -> VocabTag:
    normalized = (value or "other").casefold().strip()
    return normalized if normalized in VALID_TAGS else "other"  # type: ignore[return-value]


def _opposite_direction(direction: SuggestDirection) -> SuggestDirection:
    return "target-to-en" if direction == "en-to-target" else "en-to-target"


def _mock_suggestions(
    language: LanguageCode,
    input_text: str,
    direction: SuggestDirection,
) -> VocabSuggestResponse:
    rows = _DEV_LEXICON.get((_normalize(input_text), direction), [])
    return VocabSuggestResponse(
        candidates=[VocabSuggestion(text=text, pos=pos) for text, pos in rows],
        mock=True,
    )


def _mock_misplaced(
    input_text: str,
    direction: SuggestDirection,
) -> VocabSuggestResponse:
    rows = _DEV_MISPLACED.get((_normalize(input_text), direction), [])
    resolved = _opposite_direction(direction)
    return VocabSuggestResponse(
        candidates=[VocabSuggestion(text=text, pos=pos) for text, pos in rows],
        mock=True,
        field_swap=bool(rows),
        resolved_direction=resolved if rows else None,
    )


def _suggestion_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "text": {"type": "string"},
                        "pos": {
                            "type": "string",
                            "enum": ["noun", "verb", "adjective", "adverb", "preposition", "other"],
                        },
                    },
                    "required": ["text", "pos"],
                },
            }
        },
        "required": ["candidates"],
    }


def _enrichment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "surface_form": {"type": "string"},
            "lemma": {"type": "string"},
            "gloss_primary": {"type": "string"},
            "glosses": {"type": "array", "items": {"type": "string"}},
            "pos": {
                "type": "string",
                "enum": ["noun", "verb", "adjective", "adverb", "preposition", "other"],
            },
            "tags": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["noun", "verb", "adjective", "adverb", "preposition", "other"],
                },
            },
            "cefr": {"type": ["string", "null"]},
            "frequency_rank": {"type": ["integer", "null"]},
            "gender": {"type": ["string", "null"]},
            "conjugation_class": {"type": ["string", "null"]},
            "morph_features": {"type": ["object", "null"], "additionalProperties": True},
            "ipa": {"type": ["string", "null"]},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "surface_form",
            "lemma",
            "gloss_primary",
            "glosses",
            "pos",
            "tags",
            "cefr",
            "frequency_rank",
            "gender",
            "conjugation_class",
            "morph_features",
            "ipa",
            "notes",
        ],
    }


def _call_openai_json(prompt: str, schema_name: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_vocab_model,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise bilingual dictionary for language learners.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _parse_candidates(data: dict[str, Any]) -> list[VocabSuggestion]:
    candidates: list[VocabSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for item in data.get("candidates", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        pos = _coerce_tag(str(item.get("pos", "other")))
        key = (_normalize(text), pos)
        if text and key not in seen:
            seen.add(key)
            candidates.append(VocabSuggestion(text=text, pos=pos))
    return candidates


def _suggestion_prompt(payload: VocabSuggestRequest, language: LanguageCode) -> str:
    target = _language_name(language)
    if payload.direction == "en-to-target":
        source = "English"
        destination = target
    else:
        source = target
        destination = "English"
    return (
        f"Translate one lexical item from {source} to {destination}.\n"
        f'Input: "{payload.input_text.strip()}"\n'
        f"The input must be in {source}. If it is not in {source}, return an empty candidates list.\n"
        f"Do not translate from {destination} or any other language.\n"
        "Return only direct dictionary translations of that word or short lexical phrase.\n"
        "Return as many candidates as the input genuinely has, and no filler candidates.\n"
        "If the input is a fragment with no direct lexical translation, return an empty list.\n"
        "For broad English verbs, include only the common dictionary senses that match the exact "
        "input. For example, English 'to play' into Spanish should return jugar and tocar, "
        "not actuar unless the input explicitly says 'to play a role' or 'to act'.\n"
        "Do not return definitions, examples, explanations, inflections, or full sentences.\n"
        "Each candidate must contain only the translated lexical item and its part-of-speech tag."
    )


def _misplaced_language_prompt(payload: VocabSuggestRequest, language: LanguageCode) -> str:
    target = _language_name(language)
    if payload.direction == "target-to-en":
        wrong_field = f"{target} word field"
        expected = "English"
        destination = target
    else:
        wrong_field = "English field"
        expected = target
        destination = "English"
    opposite = _opposite_direction(payload.direction)
    return (
        f'A learner typed "{payload.input_text.strip()}" in the {wrong_field}, '
        f"but a strict {expected} lookup returned no translations.\n"
        f"Decide whether the input is actually {expected}.\n"
        f"If it is {expected}, translate it to {destination} and return direct dictionary "
        "candidates only.\n"
        f"If it is not {expected}, return an empty candidates list.\n"
        "Return as many genuine candidates as the input has, and no filler.\n"
        "Do not return definitions, examples, explanations, inflections, or full sentences.\n"
        "Each candidate must contain only the translated lexical item and its part-of-speech tag.\n"
        f"Resolved lookup direction for this case: {opposite}."
    )


def _enrichment_prompt(payload: VocabEnrichRequest, language: LanguageCode) -> str:
    target = _language_name(language)
    if payload.direction == "en-to-target":
        target_word = payload.selected_text.strip()
        english = payload.input_text.strip()
    else:
        target_word = payload.input_text.strip()
        english = payload.selected_text.strip()
    return (
        f"Create metadata for a {target} vocabulary item.\n"
        f'{target} item selected by user: "{target_word}"\n'
        f'English gloss selected by user: "{english}"\n'
        f"Known POS: {payload.pos}\n"
        "Return only metadata for this selected sense. Do not add alternate senses "
        "that are not direct glosses of the selected pair. Use null where unknown. "
        "Use CEFR only when reasonably inferable. Notes should be one short learner-facing "
        "line, ideally including a tiny example if useful."
    )


def _fallback_enrichment(payload: VocabEnrichRequest, language: LanguageCode) -> VocabEnrichResponse:
    if payload.direction == "en-to-target":
        surface = payload.selected_text.strip()
        gloss = payload.input_text.strip()
    else:
        surface = payload.input_text.strip()
        gloss = payload.selected_text.strip()
    pos = _coerce_tag(payload.pos)
    return VocabEnrichResponse(
        draft=VocabDraft(
            surface_form=surface,
            lemma=surface,
            gloss_primary=gloss,
            glosses=[gloss],
            pos=pos,
            tags=[pos],
            notes=f"Auto-prepared {surface} from a {_language_name(language)} translation suggestion.",
        ),
        mock=True,
    )


@router.post("/vocab/suggest", response_model=VocabSuggestResponse)
def suggest_vocab(
    payload: VocabSuggestRequest,
    db: Session = Depends(get_db),
) -> VocabSuggestResponse:
    language = _workspace_language(db, payload.workspace_id)
    data = _call_openai_json(
        _suggestion_prompt(payload, language),
        "vocab_suggestions",
        _suggestion_schema(),
    )
    if data is None:
        primary = _mock_suggestions(language, payload.input_text, payload.direction)
        candidates = primary.candidates
        mock = primary.mock
    else:
        candidates = _parse_candidates(data)
        mock = False

    if candidates:
        return VocabSuggestResponse(candidates=candidates, mock=mock)

    misplaced_data = _call_openai_json(
        _misplaced_language_prompt(payload, language),
        "vocab_misplaced_language",
        _suggestion_schema(),
    )
    if misplaced_data is None:
        return _mock_misplaced(payload.input_text, payload.direction)

    misplaced_candidates = _parse_candidates(misplaced_data)
    if not misplaced_candidates:
        return VocabSuggestResponse(candidates=[], mock=False)

    return VocabSuggestResponse(
        candidates=misplaced_candidates,
        mock=False,
        field_swap=True,
        resolved_direction=_opposite_direction(payload.direction),
    )


@router.post("/vocab/suggest/enrich", response_model=VocabEnrichResponse)
def enrich_vocab_suggestion(
    payload: VocabEnrichRequest,
    db: Session = Depends(get_db),
) -> VocabEnrichResponse:
    language = _workspace_language(db, payload.workspace_id)
    data = _call_openai_json(
        _enrichment_prompt(payload, language),
        "vocab_enrichment",
        _enrichment_schema(),
    )
    if data is None:
        return _fallback_enrichment(payload, language)

    pos = _coerce_tag(str(data.get("pos", payload.pos)))
    tags = [
        _coerce_tag(str(tag))
        for tag in data.get("tags", [])
        if isinstance(tag, str)
    ]
    if not tags:
        tags = [pos]
    draft = VocabDraft(
        surface_form=str(data.get("surface_form") or "").strip() or payload.selected_text.strip(),
        lemma=str(data.get("lemma") or "").strip() or payload.selected_text.strip(),
        gloss_primary=str(data.get("gloss_primary") or "").strip() or payload.input_text.strip(),
        glosses=[str(g).strip() for g in data.get("glosses", []) if str(g).strip()],
        pos=pos,
        tags=tags,
        cefr=data.get("cefr"),
        frequency_rank=data.get("frequency_rank"),
        gender=data.get("gender"),
        conjugation_class=data.get("conjugation_class"),
        morph_features=data.get("morph_features"),
        ipa=data.get("ipa"),
        notes=data.get("notes"),
    )
    if not draft.glosses:
        draft.glosses = [draft.gloss_primary]
    return VocabEnrichResponse(draft=draft, mock=False)
