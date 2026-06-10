"""Migrate existing fat Vocab rows to Lexeme + thin link."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.db.models import Lexeme, Vocab, Workspace

VALID_POS = {"noun", "verb", "adjective", "adverb", "preposition", "other"}

_LEGACY_VOCAB_COLS = (
    "lemma",
    "pos",
    "tags",
    "gloss_primary",
    "glosses",
    "cefr",
    "frequency_rank",
    "gender",
    "conjugation_class",
    "morph_features",
    "ipa",
    "audio_url",
    "image_url",
)


def normalize_key_part(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.casefold().strip().split())


def _coerce_pos(pos: str | None, tags: list[str] | None) -> str:
    if pos and pos in VALID_POS:
        return pos
    for tag in tags or []:
        if tag in VALID_POS:
            return tag
    return "other"


def _field_count(lexeme: Lexeme) -> int:
    return sum(
        1
        for value in (
            lexeme.lemma,
            lexeme.pos,
            lexeme.gloss_primary,
            lexeme.tags,
            lexeme.cefr,
            lexeme.gender,
            lexeme.ipa,
        )
        if value
    )


def is_lexeme_complete(lexeme: Lexeme) -> bool:
    return bool(
        lexeme.lemma
        and lexeme.pos
        and lexeme.gloss_primary
        and lexeme.tags
    )


def find_or_create_lexeme(
    db: Session,
    *,
    language: str,
    lemma: str,
    pos: str,
    gloss_primary: str,
    tags: list[str] | None = None,
    glosses: list[str] | None = None,
    cefr: str | None = None,
    frequency_rank: int | None = None,
    gender: str | None = None,
    conjugation_class: str | None = None,
    morph_features: dict | None = None,
    ipa: str | None = None,
    audio_url: str | None = None,
    image_url: str | None = None,
    dictionary_notes: str | None = None,
) -> Lexeme:
    norm_lemma = normalize_key_part(lemma) or lemma.strip()
    norm_pos = _coerce_pos(pos, tags)
    norm_gloss = normalize_key_part(gloss_primary)

    existing = db.scalar(
        select(Lexeme).where(
            Lexeme.language == language,
            Lexeme.lemma == norm_lemma,
            Lexeme.pos == norm_pos,
            Lexeme.gloss_primary == norm_gloss,
        )
    )
    if existing is not None:
        if tags:
            existing.tags = tags
        if glosses:
            existing.glosses = glosses
        if cefr:
            existing.cefr = cefr
        if frequency_rank is not None:
            existing.frequency_rank = frequency_rank
        if gender:
            existing.gender = gender
        if conjugation_class:
            existing.conjugation_class = conjugation_class
        if morph_features:
            existing.morph_features = morph_features
        if ipa:
            existing.ipa = ipa
        if audio_url:
            existing.audio_url = audio_url
        if image_url:
            existing.image_url = image_url
        if dictionary_notes:
            existing.dictionary_notes = dictionary_notes
        if is_lexeme_complete(existing):
            existing.enrichment_status = "complete"
            existing.enriched_at = existing.enriched_at or datetime.utcnow()
        db.add(existing)
        return existing

    lexeme = Lexeme(
        language=language,
        lemma=norm_lemma,
        pos=norm_pos,
        gloss_primary=norm_gloss,
        glosses=glosses or ([gloss_primary] if gloss_primary else []),
        tags=tags or ([norm_pos] if norm_pos else []),
        cefr=cefr,
        frequency_rank=frequency_rank,
        gender=gender,
        conjugation_class=conjugation_class,
        morph_features=morph_features,
        ipa=ipa,
        audio_url=audio_url,
        image_url=image_url,
        dictionary_notes=dictionary_notes,
        enrichment_status="pending",
    )
    if is_lexeme_complete(lexeme):
        lexeme.enrichment_status = "complete"
        lexeme.enriched_at = datetime.utcnow()
    db.add(lexeme)
    db.flush()
    return lexeme


def _legacy_vocab_columns() -> set[str]:
    inspector = inspect(engine)
    if "vocab" not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns("vocab")}


def _load_legacy_row(vocab_id: int) -> dict[str, Any]:
    cols = _legacy_vocab_columns()
    legacy = [c for c in _LEGACY_VOCAB_COLS if c in cols]
    if not legacy:
        return {}
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {', '.join(legacy)} FROM vocab WHERE id = :id"),
            {"id": vocab_id},
        ).mappings().first()
    return dict(row) if row else {}


def _lexeme_from_vocab_row(
    db: Session,
    vocab: Vocab,
    language: str,
    legacy: dict[str, Any],
) -> Lexeme:
    lemma = legacy.get("lemma") or vocab.surface_form or vocab.word
    gloss = legacy.get("gloss_primary") or vocab.translation or ""
    tags = legacy.get("tags") or []
    if isinstance(tags, str):
        import json

        tags = json.loads(tags)
    glosses = legacy.get("glosses") or []
    if isinstance(glosses, str):
        import json

        glosses = json.loads(glosses)
    pos = _coerce_pos(legacy.get("pos"), tags)
    if not tags:
        tags = [pos] if pos else []
    return find_or_create_lexeme(
        db,
        language=language,
        lemma=str(lemma),
        pos=pos,
        gloss_primary=str(gloss),
        tags=list(tags),
        glosses=list(glosses) if glosses else ([str(gloss)] if gloss else []),
        cefr=legacy.get("cefr"),
        frequency_rank=legacy.get("frequency_rank"),
        gender=legacy.get("gender"),
        conjugation_class=legacy.get("conjugation_class"),
        morph_features=legacy.get("morph_features"),
        ipa=legacy.get("ipa"),
        audio_url=legacy.get("audio_url"),
        image_url=legacy.get("image_url"),
    )


def backfill_lexemes() -> int:
    """Link vocab rows without lexeme_id to shared Lexeme entries."""
    linked = 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(Vocab).where(Vocab.lexeme_id.is_(None))
        ).all()
        for vocab in rows:
            workspace = db.get(Workspace, vocab.workspace_id)
            if workspace is None:
                continue
            legacy = _load_legacy_row(vocab.id)
            lexeme = _lexeme_from_vocab_row(db, vocab, workspace.language, legacy)
            vocab.lexeme_id = lexeme.id
            if not vocab.surface_form:
                vocab.surface_form = vocab.word
            if not vocab.surface_forms:
                vocab.surface_forms = [vocab.surface_form or vocab.word]
            gloss = str(legacy.get("gloss_primary") or vocab.translation or "")
            if gloss and lexeme.gloss_primary and gloss != lexeme.gloss_primary:
                vocab.gloss_override = gloss
            vocab.word = vocab.surface_form or vocab.word
            vocab.translation = vocab.gloss_override or lexeme.gloss_primary or gloss
            db.add(vocab)
            linked += 1
        if linked:
            db.commit()
    return linked
