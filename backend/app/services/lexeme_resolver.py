"""Resolve or create shared Lexeme entries for vocab capture."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.backfill_lexemes import find_or_create_lexeme, normalize_key_part
from app.db.models import Lexeme, Vocab

VALID_POS = {"noun", "verb", "adjective", "adverb", "preposition", "other"}


def _coerce_pos(pos: str | None, tags: list[str] | None) -> str:
    if pos and pos in VALID_POS:
        return pos
    for tag in tags or []:
        if tag in VALID_POS:
            return tag
    return "other"


def resolve_lexeme(
    db: Session,
    language: str,
    *,
    surface_form: str,
    lemma: str | None = None,
    pos: str | None = None,
    gloss_primary: str | None = None,
    tags: list[str] | None = None,
    glosses: list[str] | None = None,
    cefr: str | None = None,
    frequency_rank: int | None = None,
    gender: str | None = None,
    conjugation_class: str | None = None,
    morph_features: dict[str, Any] | None = None,
    ipa: str | None = None,
    audio_url: str | None = None,
    image_url: str | None = None,
    dictionary_notes: str | None = None,
) -> Lexeme:
    resolved_lemma = normalize_key_part(lemma or surface_form) or surface_form.strip()
    resolved_pos = _coerce_pos(pos, tags)
    resolved_gloss = normalize_key_part(gloss_primary or "")
    resolved_tags = list(tags or []) or ([resolved_pos] if resolved_pos else [])
    return find_or_create_lexeme(
        db,
        language=language,
        lemma=resolved_lemma,
        pos=resolved_pos,
        gloss_primary=resolved_gloss,
        tags=resolved_tags,
        glosses=glosses or ([gloss_primary] if gloss_primary else []),
        cefr=cefr,
        frequency_rank=frequency_rank,
        gender=gender,
        conjugation_class=conjugation_class,
        morph_features=morph_features,
        ipa=ipa,
        audio_url=audio_url,
        image_url=image_url,
        dictionary_notes=dictionary_notes,
    )


def find_vocab_link(
    db: Session,
    workspace_id: int,
    lexeme_id: int,
) -> Vocab | None:
    return db.scalar(
        select(Vocab).where(
            Vocab.workspace_id == workspace_id,
            Vocab.lexeme_id == lexeme_id,
        )
    )


def lexeme_lemma(vocab: Vocab) -> str:
    lexeme = getattr(vocab, "lexeme", None)
    if lexeme is not None and lexeme.lemma:
        return lexeme.lemma
    legacy = getattr(vocab, "lemma", None)
    return legacy or vocab.surface_form or vocab.word
