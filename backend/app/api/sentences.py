"""Sentence persistence and retrieval (LOS-501).

Sentences are first-class atoms with token-level links to vocab. Generation
happens in :mod:`app.api.generate`; this module only handles storage and
queries used by Word Home, sentences page, and any future review surfaces.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.vocab import _ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Sentence, SentenceWordLink, Vocab
from app.db.schemas import SentenceCreate, SentenceListResponse, SentenceOut

router = APIRouter()


@router.post("/sentences", response_model=SentenceOut)
def create_sentence(payload: SentenceCreate, db: Session = Depends(get_db)) -> SentenceOut:
    _ensure_workspace_owner(db, payload.workspace_id)

    # Validate every link refers to a vocab in the same workspace.
    if payload.links:
        ids = [link.vocab_id for link in payload.links]
        rows = db.scalars(select(Vocab).where(Vocab.id.in_(ids))).all()
        by_id = {row.id: row for row in rows}
        for link in payload.links:
            row = by_id.get(link.vocab_id)
            if row is None or row.workspace_id != payload.workspace_id:
                raise HTTPException(
                    status_code=422,
                    detail=f"vocab_id {link.vocab_id} not in workspace",
                )

    sentence = Sentence(
        workspace_id=payload.workspace_id,
        text=payload.text,
        translation=payload.translation,
        language=payload.language,
        source=payload.source,
        source_meta=payload.source_meta,
        score=payload.score,
        links=[
            SentenceWordLink(
                vocab_id=link.vocab_id,
                surface_token=link.surface_token,
                position=link.position,
                role=link.role,
            )
            for link in payload.links
        ],
    )
    db.add(sentence)
    db.commit()
    db.refresh(sentence)
    return SentenceOut.model_validate(sentence)


@router.get("/sentences", response_model=SentenceListResponse)
def list_sentences(
    workspace_id: int = Query(..., ge=1),
    vocab_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> SentenceListResponse:
    _ensure_workspace_owner(db, workspace_id)
    query = (
        select(Sentence)
        .options(selectinload(Sentence.links))
        .where(Sentence.workspace_id == workspace_id)
        .order_by(Sentence.created_at.desc())
        .limit(limit)
    )
    if vocab_id is not None:
        query = query.join(Sentence.links).where(SentenceWordLink.vocab_id == vocab_id)
    items = db.scalars(query).unique().all()
    return SentenceListResponse(items=[SentenceOut.model_validate(s) for s in items])


@router.get("/sentences/{sentence_id}", response_model=SentenceOut)
def get_sentence(sentence_id: int, db: Session = Depends(get_db)) -> SentenceOut:
    sentence = db.scalar(
        select(Sentence)
        .options(selectinload(Sentence.links))
        .where(Sentence.id == sentence_id)
    )
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    _ensure_workspace_owner(db, sentence.workspace_id)
    return SentenceOut.model_validate(sentence)


@router.delete("/sentences/{sentence_id}")
def delete_sentence(sentence_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    sentence = db.get(Sentence, sentence_id)
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    _ensure_workspace_owner(db, sentence.workspace_id)
    db.delete(sentence)
    db.commit()
    return {"ok": True}
