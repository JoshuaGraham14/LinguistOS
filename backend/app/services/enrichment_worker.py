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
from app.services.enrichment import (
    apply_enrichment_to_lexeme,
    enrich_lexeme_llm,
    find_complete_lexeme_match,
    find_lexeme_with_sense_key,
    mark_lexeme_enriched,
    merge_duplicate_lexeme_into,
    missing_lexeme_fields,
    needs_enrichment,
)

logger = logging.getLogger(__name__)

_sweeper_thread: threading.Thread | None = None
_startup_thread: threading.Thread | None = None


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
        merge_duplicate_lexeme_into(db, lexeme, cached)
        job.status = "done"
        job.result = {"source": "cache", "lexeme_id": cached.id}
        job.confidence = 1.0
        job.completed_at = datetime.utcnow()
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

    apply_enrichment_to_lexeme(lexeme, result)
    collision = find_lexeme_with_sense_key(
        db,
        language=lexeme.language,
        lemma=lexeme.lemma,
        pos=lexeme.pos,
        gloss_primary=lexeme.gloss_primary,
        exclude_id=lexeme.id,
    )
    if collision is not None:
        merge_duplicate_lexeme_into(db, lexeme, collision)
        job.status = "done"
        job.result = {"source": "dedupe", "lexeme_id": collision.id}
        job.confidence = confidence
        job.completed_at = datetime.utcnow()
        db.add(job)
        return

    mark_lexeme_enriched(lexeme)
    job.status = "done"
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
            .where(Lexeme.enrichment_status.in_(("pending", "complete")))
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
    """Enqueue and process enrichment work without blocking API startup."""
    global _startup_thread
    if _startup_thread is not None and _startup_thread.is_alive():
        return

    def _run() -> None:
        try:
            sweep_incomplete_lexemes()
            process_pending_jobs()
        except Exception:
            logger.exception("Startup enrichment failed")

    _startup_thread = threading.Thread(
        target=_run,
        name="lexeme-startup-enrichment",
        daemon=True,
    )
    _startup_thread.start()
