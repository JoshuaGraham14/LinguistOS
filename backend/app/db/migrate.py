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


def migrate_enrichment_jobs_for_lexeme(engine: Engine) -> bool:
    """Rebuild enrichment_jobs so vocab_id is nullable and lexeme_id exists.

    SQLite cannot relax NOT NULL on an existing column; rebuild the table
    when upgrading from the pre-Lexeme schema.
    """
    inspector = inspect(engine)
    if "enrichment_jobs" not in inspector.get_table_names():
        return False

    cols = {col["name"]: col for col in inspector.get_columns("enrichment_jobs")}
    vocab_col = cols.get("vocab_id")
    needs_rebuild = vocab_col is not None and not vocab_col.get("nullable", True)
    needs_rebuild = needs_rebuild or "lexeme_id" not in cols
    if not needs_rebuild:
        return False

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE enrichment_jobs_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lexeme_id INTEGER REFERENCES lexemes(id),
                    vocab_id INTEGER REFERENCES vocab(id),
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    requested_fields JSON NOT NULL DEFAULT '[]',
                    result JSON,
                    confidence FLOAT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
                """
            )
        )
        if "lexeme_id" in cols:
            conn.execute(
                text(
                    """
                    INSERT INTO enrichment_jobs_new (
                        id, lexeme_id, vocab_id, status, requested_fields,
                        result, confidence, created_at, completed_at
                    )
                    SELECT
                        id, lexeme_id, vocab_id, status, requested_fields,
                        result, confidence, created_at, completed_at
                    FROM enrichment_jobs
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO enrichment_jobs_new (
                        id, vocab_id, status, requested_fields,
                        result, confidence, created_at, completed_at
                    )
                    SELECT
                        id, vocab_id, status, requested_fields,
                        result, confidence, created_at, completed_at
                    FROM enrichment_jobs
                    """
                )
            )
        conn.execute(text("DROP TABLE enrichment_jobs"))
        conn.execute(text("ALTER TABLE enrichment_jobs_new RENAME TO enrichment_jobs"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_enrichment_lexeme_status "
                "ON enrichment_jobs (lexeme_id, status)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_enrichment_vocab_status "
                "ON enrichment_jobs (vocab_id, status)"
            )
        )
    return True


def migrate_complete_to_enriched(engine: Engine) -> int:
    """Promote legacy complete lexemes that should skip future LLM sweeps."""
    inspector = inspect(engine)
    if "lexemes" not in inspector.get_table_names():
        return 0
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE lexemes
                SET enrichment_status = 'enriched'
                WHERE enrichment_status = 'complete'
                  AND (
                    dictionary_notes IS NOT NULL
                    OR cefr IS NOT NULL
                    OR ipa IS NOT NULL
                    OR gender IS NOT NULL
                    OR morph_features IS NOT NULL
                    OR pos NOT IN ('', 'other')
                  )
                """
            )
        )
        return result.rowcount or 0


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
