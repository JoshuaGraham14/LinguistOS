"""Background enrichment job processing and sweeper."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import EnrichmentJob, Lexeme, Vocab
from app.services.enrichment import (
    apply_enrichment_to_lexeme,
    copy_lexeme_fields,
    enrich_lexeme_llm,
    find_complete_lexeme_match,
    is_lexeme_complete,
    missing_lexeme_fields,
)

logger = logging.getLogger(__name__)

_sweeper_task: asyncio.Task[None] | None = None


def maybe_enqueue_enrichment(
    db: Session,
    *,
    lexeme_id: int,
    vocab_id: int | None = None,
) -> EnrichmentJob | None:
    lexeme = db.get(Lexeme, lexeme_id)
    if lexeme is None or is_lexeme_complete(lexeme):
        return None

    pending = db.scalar(
        select(EnrichmentJob).where(
            EnrichmentJob.lexeme_id == lexeme_id,
            EnrichmentJob.status == "pending",
        )
    )
    if pending is not None:
        return pending

    job = EnrichmentJob(
        lexeme_id=lexeme_id,
        vocab_id=vocab_id,
        status="pending",
        requested_fields=missing_lexeme_fields(lexeme),
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

    if is_lexeme_complete(lexeme):
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
            .where(Lexeme.enrichment_status != "complete")
            .limit(limit)
        ).all()
        for lexeme in lexemes:
            if maybe_enqueue_enrichment(db, lexeme_id=lexeme.id) is not None:
                enqueued += 1
        if enqueued:
            db.commit()
    return enqueued


async def _sweeper_loop() -> None:
    while True:
        try:
            sweep_incomplete_lexemes()
            process_pending_jobs()
        except Exception:
            logger.exception("Enrichment sweeper iteration failed")
        await asyncio.sleep(3600)


def start_enrichment_scheduler() -> None:
    global _sweeper_task
    if _sweeper_task is not None and not _sweeper_task.done():
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            _sweeper_task = asyncio.create_task(_sweeper_loop())
    except RuntimeError:
        pass


def run_startup_enrichment() -> None:
    sweep_incomplete_lexemes()
    process_pending_jobs()
