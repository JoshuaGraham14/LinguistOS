"""Lightweight dev-time schema migrations.

Compensates for the fact that ``Base.metadata.create_all`` does not add new
columns to tables that already exist. Specifically, when LOS-101 added new
canonical fields to ``vocab`` and we shipped new ``word_mastery`` and
``enrichment_jobs`` tables, existing dev SQLite databases need to be brought
forward without losing data.

This module is intentionally minimal and idempotent. For production,
replace with Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# Each entry is (column_name, SQL type for ADD COLUMN, default literal or None).
_LEXEME_VOCAB_COLUMNS: list[tuple[str, str, str | None]] = [
    ("lexeme_id", "INTEGER", None),
    ("gloss_override", "VARCHAR(255)", None),
]

_ENRICHMENT_JOB_COLUMNS: list[tuple[str, str, str | None]] = [
    ("lexeme_id", "INTEGER", None),
]

_VOCAB_COLUMNS: list[tuple[str, str, str | None]] = [
    ("lemma", "VARCHAR(255)", None),
    ("surface_form", "VARCHAR(255)", None),
    ("surface_forms", "JSON", "'[]'"),
    ("pos", "VARCHAR(32)", None),
    ("cefr", "VARCHAR(8)", None),
    ("frequency_rank", "INTEGER", None),
    ("gender", "VARCHAR(8)", None),
    ("conjugation_class", "VARCHAR(32)", None),
    ("morph_features", "JSON", None),
    ("ipa", "VARCHAR(128)", None),
    ("audio_url", "VARCHAR(512)", None),
    ("image_url", "VARCHAR(512)", None),
    ("gloss_primary", "VARCHAR(255)", None),
    ("glosses", "JSON", "'[]'"),
    ("notes", "TEXT", None),
    ("last_seen_at", "DATETIME", None),
]


def _add_missing_columns(
    engine: Engine,
    table: str,
    columns: list[tuple[str, str, str | None]],
) -> list[str]:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return []
    existing = {col["name"] for col in inspector.get_columns(table)}
    added: list[str] = []
    with engine.begin() as conn:
        for name, sql_type, default in columns:
            if name in existing:
                continue
            default_clause = f" DEFAULT {default}" if default is not None else ""
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}{default_clause}")
            )
            added.append(name)
    return added


def ensure_lexeme_vocab_columns(engine: Engine) -> list[str]:
    """Add lexeme_id and gloss_override to an existing vocab table."""
    return _add_missing_columns(engine, "vocab", _LEXEME_VOCAB_COLUMNS)


def ensure_enrichment_job_lexeme_column(engine: Engine) -> list[str]:
    """Add lexeme_id to an existing enrichment_jobs table."""
    return _add_missing_columns(engine, "enrichment_jobs", _ENRICHMENT_JOB_COLUMNS)


def ensure_vocab_canonical_columns(engine: Engine) -> list[str]:
    """Add any LOS-101 columns missing from an existing ``vocab`` table.

    Returns the list of column names added.
    """
    return _add_missing_columns(engine, "vocab", _VOCAB_COLUMNS)


_DEPRECATED_VOCAB_COLUMNS: tuple[str, ...] = (
    "tags",
    "lemma",
    "pos",
    "cefr",
    "frequency_rank",
    "gender",
    "conjugation_class",
    "morph_features",
    "ipa",
    "audio_url",
    "image_url",
    "gloss_primary",
    "glosses",
)


def drop_deprecated_vocab_columns(engine: Engine) -> list[str]:
    """Drop linguistic columns migrated to Lexeme (SQLite 3.35+)."""
    inspector = inspect(engine)
    if "vocab" not in inspector.get_table_names():
        return []
    existing = {col["name"] for col in inspector.get_columns("vocab")}
    dropped: list[str] = []
    with engine.begin() as conn:
        for name in _DEPRECATED_VOCAB_COLUMNS:
            if name not in existing:
                continue
            conn.execute(text(f"ALTER TABLE vocab DROP COLUMN {name}"))
            dropped.append(name)
    return dropped
