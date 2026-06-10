"""Background enrichment job processing and sweeper."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import EnrichmentJob, Lexeme, Vocab
from sqlalchemy import and_, or_

from app.services.enrichment import (
    apply_enrichment_to_lexeme,
    copy_lexeme_fields,
    enrich_lexeme_llm,
    find_complete_lexeme_match,
    missing_lexeme_fields,
    needs_enrichment,
)

logger = logging.getLogger(__name__)

_sweeper_thread: threading.Thread | None = None


def maybe_enqueue_enrichment(
    db: Session,
    *,
    lexeme_id: int,
    vocab_id: int | None = None,
) -> EnrichmentJob | None:
    lexeme = db.get(Lexeme, lexeme_id)
    if lexeme is None or not needs_enrichment(lexeme):
        return None

    pending = db.scalar(
        select(EnrichmentJob).where(
            EnrichmentJob.lexeme_id == lexeme_id,
            EnrichmentJob.status == "pending",
        )
    )
    if pending is not None:
        return pending

    missing = missing_lexeme_fields(lexeme)
    if not missing and lexeme.enrichment_status == "complete":
        missing = ["cefr", "gender", "ipa", "dictionary_notes"]
    job = EnrichmentJob(
        lexeme_id=lexeme_id,
        vocab_id=vocab_id,
        status="pending",
        requested_fields=missing,
    )
    db.add(job)
    db.flush()
    return job


def process_enrichment_job(db: Session, job_id: int) -> None:
    job = db.get(EnrichmentJob, job_id)
    if job is None or job.status != "pending" or job.lexeme_id is None:
        return

    lexeme = db.get(Lexeme, job.lexeme_id)
    if lexeme is None:
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        db.add(job)
        return

    if not needs_enrichment(lexeme):
        job.status = "done"
        job.completed_at = datetime.utcnow()
        db.add(job)
        return

    cached = find_complete_lexeme_match(db, lexeme)
    if cached is not None and cached.id != lexeme.id:
        copy_lexeme_fields(lexeme, cached)
        job.status = "done"
        job.result = {"source": "cache", "lexeme_id": cached.id}
        job.confidence = 1.0
        job.completed_at = datetime.utcnow()
        db.add(lexeme)
        db.add(job)
        return

    surface = lexeme.lemma
    gloss = lexeme.gloss_primary
    vocab = db.get(Vocab, job.vocab_id) if job.vocab_id else None
    if vocab is not None:
        surface = vocab.surface_form or surface
        gloss = vocab.gloss_override or gloss or vocab.translation

    result, confidence, _mock = enrich_lexeme_llm(
        language=lexeme.language,  # type: ignore[arg-type]
        target_word=surface,
        english_gloss=gloss,
        pos=lexeme.pos,
    )

    if confidence >= 0.85:
        apply_enrichment_to_lexeme(lexeme, result)
        job.status = "done"
    else:
        job.status = "done"
        apply_enrichment_to_lexeme(lexeme, result)

    job.result = result
    job.confidence = confidence
    job.completed_at = datetime.utcnow()
    db.add(lexeme)
    db.add(job)


def process_pending_jobs(limit: int = 20) -> int:
    processed = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(EnrichmentJob)
            .where(EnrichmentJob.status == "pending")
            .order_by(EnrichmentJob.created_at)
            .limit(limit)
        ).all()
        for job in jobs:
            process_enrichment_job(db, job.id)
            processed += 1
        if processed:
            db.commit()
    return processed


def sweep_incomplete_lexemes(limit: int = 50) -> int:
    enqueued = 0
    with SessionLocal() as db:
        lexemes = db.scalars(
            select(Lexeme)
            .where(
                or_(
                    Lexeme.enrichment_status != "complete",
                    and_(
                        Lexeme.enrichment_status == "complete",
                        Lexeme.dictionary_notes.is_(None),
                        Lexeme.cefr.is_(None),
                        Lexeme.ipa.is_(None),
                        Lexeme.gender.is_(None),
                        # Legacy thin rows auto-marked complete; skip seeded lexemes
                        # that already have real POS tags.
                        Lexeme.pos.in_(["", "other"]),
                    ),
                )
            )
            .limit(limit)
        ).all()
        for lexeme in lexemes:
            if maybe_enqueue_enrichment(db, lexeme_id=lexeme.id) is not None:
                enqueued += 1
        if enqueued:
            db.commit()
    return enqueued


def _sweeper_loop() -> None:
    while True:
        time.sleep(3600)
        try:
            sweep_incomplete_lexemes()
            process_pending_jobs()
        except Exception:
            logger.exception("Enrichment sweeper iteration failed")


def start_enrichment_scheduler() -> None:
    global _sweeper_thread
    if _sweeper_thread is not None and _sweeper_thread.is_alive():
        return
    _sweeper_thread = threading.Thread(target=_sweeper_loop, name="lexeme-sweeper", daemon=True)
    _sweeper_thread.start()


def run_startup_enrichment() -> None:
    sweep_incomplete_lexemes()
    process_pending_jobs()
