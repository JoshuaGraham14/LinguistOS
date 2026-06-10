"""Lexeme resolver and sense-key deduplication."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.backfill_lexemes import find_or_create_lexeme, normalize_key_part
from app.db.database import SessionLocal
from app.db.models import Lexeme


def test_normalize_key_part_collapses_whitespace() -> None:
    assert normalize_key_part("  Banco   ") == "banco"


def test_find_or_create_lexeme_dedupes_same_sense() -> None:
    with SessionLocal() as db:
        first = find_or_create_lexeme(
            db,
            language="es",
            lemma="perro",
            pos="noun",
            gloss_primary="dog",
            tags=["noun"],
        )
        second = find_or_create_lexeme(
            db,
            language="es",
            lemma="perro",
            pos="noun",
            gloss_primary="dog",
            tags=["noun"],
        )
        db.commit()
        assert first.id == second.id


def test_find_or_create_lexeme_separates_homonyms() -> None:
    with SessionLocal() as db:
        bank = find_or_create_lexeme(
            db,
            language="es",
            lemma="banco",
            pos="noun",
            gloss_primary="bank",
            tags=["noun"],
        )
        bench = find_or_create_lexeme(
            db,
            language="es",
            lemma="banco",
            pos="noun",
            gloss_primary="bench",
            tags=["noun"],
        )
        db.commit()
        assert bank.id != bench.id
        count = db.scalar(
            select(func.count()).select_from(Lexeme).where(Lexeme.lemma == "banco")
        )
        assert count == 2
