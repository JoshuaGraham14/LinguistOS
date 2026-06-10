"""Lexeme enrichment completeness and worker behaviour."""

from __future__ import annotations

from app.db.backfill_lexemes import find_or_create_lexeme, is_lexeme_complete
from app.db.database import SessionLocal
from app.db.models import EnrichmentJob, Lexeme, Vocab, Workspace
from app.services.enrichment import apply_enrichment_to_lexeme, missing_lexeme_fields
from app.services.enrichment_worker import maybe_enqueue_enrichment, process_enrichment_job


def test_missing_lexeme_fields_detects_gaps() -> None:
    lexeme = Lexeme(
        language="es",
        lemma="hablo",
        pos="verb",
        gloss_primary="",
        tags=[],
    )
    missing = missing_lexeme_fields(lexeme)
    assert "gloss_primary" in missing
    assert "tags" in missing


def test_apply_enrichment_marks_complete() -> None:
    lexeme = Lexeme(
        language="es",
        lemma="comer",
        pos="verb",
        gloss_primary="",
        tags=[],
    )
    apply_enrichment_to_lexeme(
        lexeme,
        {
            "lemma": "comer",
            "pos": "verb",
            "gloss_primary": "to eat",
            "tags": ["verb"],
            "glosses": ["to eat"],
        },
    )
    assert is_lexeme_complete(lexeme)
    assert lexeme.enrichment_status == "complete"


def test_process_enrichment_job_uses_mock_without_api_key(client, workspace) -> None:
    wid = workspace["id"]
    with SessionLocal() as db:
        ws = db.get(Workspace, wid)
        assert ws is not None
        lexeme = find_or_create_lexeme(
            db,
            language=ws.language,
            lemma="nadar",
            pos="other",
            gloss_primary="",
            tags=[],
        )
        vocab = Vocab(
            workspace_id=wid,
            lexeme_id=lexeme.id,
            word="Nadar",
            translation="to swim",
            surface_form="Nadar",
            surface_forms=["Nadar"],
            gloss_override="to swim",
        )
        db.add(vocab)
        db.flush()
        job = maybe_enqueue_enrichment(db, lexeme_id=lexeme.id, vocab_id=vocab.id)
        assert job is not None
        db.commit()
        process_enrichment_job(db, job.id)
        db.commit()
        refreshed = db.get(Lexeme, lexeme.id)
        assert refreshed is not None
        assert refreshed.enrichment_status == "complete"
        assert refreshed.gloss_primary == "to swim"
        done = db.get(EnrichmentJob, job.id)
        assert done is not None
        assert done.status == "done"
