"""Lexeme enrichment via LLM and completeness checks."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.backfill_lexemes import is_lexeme_complete, normalize_key_part
from app.db.models import Lexeme
from app.db.schemas import LanguageCode, VocabTag

LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish",
    "fr": "French",
    "he": "Hebrew",
}

VALID_TAGS: set[str] = {"noun", "verb", "adjective", "adverb", "preposition", "other"}

REQUIRED_FIELDS = ("lemma", "pos", "tags", "gloss_primary")


def _coerce_tag(value: str | None) -> VocabTag:
    normalized = (value or "other").casefold().strip()
    return normalized if normalized in VALID_TAGS else "other"  # type: ignore[return-value]


def missing_lexeme_fields(lexeme: Lexeme) -> list[str]:
    missing: list[str] = []
    if not lexeme.lemma:
        missing.append("lemma")
    if not lexeme.pos:
        missing.append("pos")
    if not lexeme.tags:
        missing.append("tags")
    if not lexeme.gloss_primary:
        missing.append("gloss_primary")
    return missing


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


def _enrichment_prompt(
    *,
    language: LanguageCode,
    target_word: str,
    english_gloss: str,
    pos: str,
) -> str:
    target = LANGUAGE_NAMES.get(language, language)
    return (
        f"Create metadata for a {target} vocabulary item.\n"
        f'{target} item selected by user: "{target_word}"\n'
        f'English gloss selected by user: "{english_gloss}"\n'
        f"Known POS: {pos}\n"
        "Return only metadata for this selected sense. Do not add alternate senses "
        "that are not direct glosses of the selected pair. Use null where unknown. "
        "Use CEFR only when reasonably inferable. Notes should be one short learner-facing "
        "line, ideally including a tiny example if useful."
    )


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
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
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


def _fallback_enrichment(
    *,
    target_word: str,
    english_gloss: str,
    pos: str,
    language: LanguageCode,
) -> dict[str, Any]:
    coerced = _coerce_tag(pos)
    target = LANGUAGE_NAMES.get(language, language)
    return {
        "surface_form": target_word,
        "lemma": target_word,
        "gloss_primary": english_gloss,
        "glosses": [english_gloss] if english_gloss else [],
        "pos": coerced,
        "tags": [coerced],
        "cefr": None,
        "frequency_rank": None,
        "gender": None,
        "conjugation_class": None,
        "morph_features": None,
        "ipa": None,
        "notes": f"Auto-prepared {target_word} from a {target} translation suggestion.",
    }


def enrich_lexeme_llm(
    *,
    language: LanguageCode,
    target_word: str,
    english_gloss: str,
    pos: str,
) -> tuple[dict[str, Any], float, bool]:
    """Return (result dict, confidence, used_mock)."""
    data = _call_openai_json(
        _enrichment_prompt(
            language=language,
            target_word=target_word,
            english_gloss=english_gloss,
            pos=pos,
        ),
        "vocab_enrichment",
        _enrichment_schema(),
    )
    if data is None:
        return (
            _fallback_enrichment(
                target_word=target_word,
                english_gloss=english_gloss,
                pos=pos,
                language=language,
            ),
            0.5,
            True,
        )
    pos_val = _coerce_tag(str(data.get("pos", pos)))
    tags = [_coerce_tag(str(tag)) for tag in data.get("tags", []) if isinstance(tag, str)]
    if not tags:
        tags = [pos_val]
    gloss_primary = str(data.get("gloss_primary") or "").strip() or english_gloss
    glosses = [str(g).strip() for g in data.get("glosses", []) if str(g).strip()]
    if not glosses and gloss_primary:
        glosses = [gloss_primary]
    result = {
        "lemma": str(data.get("lemma") or "").strip() or target_word,
        "gloss_primary": gloss_primary,
        "glosses": glosses,
        "pos": pos_val,
        "tags": tags,
        "cefr": data.get("cefr"),
        "frequency_rank": data.get("frequency_rank"),
        "gender": data.get("gender"),
        "conjugation_class": data.get("conjugation_class"),
        "morph_features": data.get("morph_features"),
        "ipa": data.get("ipa"),
        "dictionary_notes": data.get("notes"),
    }
    return result, 0.9, False


def apply_enrichment_to_lexeme(lexeme: Lexeme, result: dict[str, Any]) -> None:
    if result.get("lemma"):
        lexeme.lemma = normalize_key_part(str(result["lemma"])) or str(result["lemma"]).strip()
    if result.get("pos"):
        lexeme.pos = str(result["pos"])
    if result.get("tags"):
        lexeme.tags = list(result["tags"])
    if result.get("gloss_primary"):
        lexeme.gloss_primary = normalize_key_part(str(result["gloss_primary"]))
    if result.get("glosses"):
        lexeme.glosses = list(result["glosses"])
    for field in ("cefr", "gender", "conjugation_class", "ipa"):
        if result.get(field):
            setattr(lexeme, field, result[field])
    if result.get("frequency_rank") is not None:
        lexeme.frequency_rank = result["frequency_rank"]
    if result.get("morph_features"):
        lexeme.morph_features = result["morph_features"]
    if result.get("dictionary_notes"):
        lexeme.dictionary_notes = str(result["dictionary_notes"])
    if is_lexeme_complete(lexeme):
        lexeme.enrichment_status = "complete"
        lexeme.enriched_at = datetime.utcnow()
    else:
        lexeme.enrichment_status = "pending"


def find_complete_lexeme_match(db: Session, lexeme: Lexeme) -> Lexeme | None:
    if is_lexeme_complete(lexeme):
        return lexeme
    return db.scalar(
        select(Lexeme).where(
            Lexeme.language == lexeme.language,
            Lexeme.lemma == lexeme.lemma,
            Lexeme.pos == lexeme.pos,
            Lexeme.gloss_primary == lexeme.gloss_primary,
            Lexeme.enrichment_status == "complete",
            Lexeme.id != lexeme.id,
        )
    )


def copy_lexeme_fields(target: Lexeme, source: Lexeme) -> None:
    target.lemma = source.lemma
    target.pos = source.pos
    target.gloss_primary = source.gloss_primary
    target.glosses = list(source.glosses or [])
    target.tags = list(source.tags or [])
    target.cefr = source.cefr
    target.frequency_rank = source.frequency_rank
    target.gender = source.gender
    target.conjugation_class = source.conjugation_class
    target.morph_features = source.morph_features
    target.ipa = source.ipa
    target.audio_url = source.audio_url
    target.image_url = source.image_url
    target.dictionary_notes = source.dictionary_notes
    target.enrichment_status = "complete"
    target.enriched_at = source.enriched_at or datetime.utcnow()
