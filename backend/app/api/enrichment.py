"""Enrichment status and manual enqueue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api._auth import ensure_workspace_owner
from app.db.database import SessionLocal, get_db
from app.db.models import Lexeme, Vocab
from app.db.schemas import EnrichmentJobOut, LexemeOut
from app.services.enrichment import missing_lexeme_fields
from app.services.enrichment_worker import maybe_enqueue_enrichment, process_enrichment_job

router = APIRouter()


def _process_job(job_id: int) -> None:
    with SessionLocal() as db:
        process_enrichment_job(db, job_id)
        db.commit()


@router.get("/lexemes/{lexeme_id}", response_model=LexemeOut)
def get_lexeme(lexeme_id: int, db: Session = Depends(get_db)) -> LexemeOut:
    lexeme = db.get(Lexeme, lexeme_id)
    if lexeme is None:
        raise HTTPException(status_code=404, detail="Lexeme not found")
    return LexemeOut.model_validate(lexeme)


@router.get("/lexemes/{lexeme_id}/enrichment")
def lexeme_enrichment_status(lexeme_id: int, db: Session = Depends(get_db)) -> dict:
    lexeme = db.get(Lexeme, lexeme_id)
    if lexeme is None:
        raise HTTPException(status_code=404, detail="Lexeme not found")
    return {
        "lexeme_id": lexeme.id,
        "enrichment_status": lexeme.enrichment_status,
        "missing_fields": missing_lexeme_fields(lexeme),
        "enriched_at": lexeme.enriched_at,
    }


@router.post("/enrichment/vocab/{vocab_id}", response_model=EnrichmentJobOut)
def enqueue_vocab_enrichment(
    vocab_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> EnrichmentJobOut:
    item = db.scalar(
        select(Vocab)
        .options(selectinload(Vocab.lexeme))
        .where(Vocab.id == vocab_id)
    )
    if item is None or item.lexeme_id is None:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)

    job = maybe_enqueue_enrichment(db, lexeme_id=item.lexeme_id, vocab_id=item.id)
    if job is None:
        raise HTTPException(status_code=409, detail="Lexeme already complete")
    db.commit()
    db.refresh(job)
    background_tasks.add_task(_process_job, job.id)
    return EnrichmentJobOut.model_validate(job)
