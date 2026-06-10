"""Token resolution and token actions (MVP+ thin)."""

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api._auth import ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Vocab, WordOccurrence, Workspace
from app.db.schemas import (
    TokenActionRequest,
    TokenActionResponse,
    TokenCandidate,
    TokenResolveRequest,
    TokenResolveResponse,
    TokenSpanOut,
)
from app.services.enrichment_worker import maybe_enqueue_enrichment, process_enrichment_job
from app.services.lexeme_resolver import lexeme_lemma, resolve_lexeme
from app.services.vocab_mapper import sync_legacy_mirrors, vocab_out

router = APIRouter()


def _run_token_enrichment(job_id: int) -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        process_enrichment_job(db, job_id)
        db.commit()

_TOKEN_RE = re.compile(r"[\w\u00C0-\u017F']+")


def _normalize(token: str) -> str:
    return re.sub(r"[.,!?¿¡;:\"“”()\[\]{}]", "", token.strip().lower())


def _tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for match in _TOKEN_RE.finditer(text):
        out.append((match.group(0), match.start(), match.end()))
    return out


def _matches_vocab(vocab: Vocab, normalized: str) -> bool:
    forms = [vocab.word, vocab.surface_form or "", *(vocab.surface_forms or [])]
    if vocab.lexeme:
        forms.append(vocab.lexeme.lemma)
    return any(_normalize(form) == normalized for form in forms if form)


def _load_vocab_rows(db: Session, workspace_id: int) -> list[Vocab]:
    return list(
        db.scalars(
            select(Vocab)
            .options(selectinload(Vocab.lexeme))
            .where(Vocab.workspace_id == workspace_id)
        ).all()
    )


@router.post("/tokens/resolve", response_model=TokenResolveResponse)
def resolve_tokens(
    payload: TokenResolveRequest,
    db: Session = Depends(get_db),
) -> TokenResolveResponse:
    ensure_workspace_owner(db, payload.workspace_id)
    rows = _load_vocab_rows(db, payload.workspace_id)

    spans: list[TokenSpanOut] = []
    for token, start, end in _tokenize_with_spans(payload.text):
        normalized = _normalize(token)
        if not normalized:
            continue
        candidates = [r for r in rows if _matches_vocab(r, normalized)]
        candidate_out = [
            TokenCandidate(
                vocab_id=c.id,
                word=c.word,
                lemma=lexeme_lemma(c) if c.lexeme else c.surface_form,
                surface_form=c.surface_form,
                translation=c.translation,
            )
            for c in candidates
        ]
        vocab_id = candidates[0].id if len(candidates) == 1 else None
        confidence = 1.0 if len(candidates) == 1 else (0.5 if candidates else 0.0)
        spans.append(
            TokenSpanOut(
                token=token,
                start=start,
                end=end,
                normalized=normalized,
                vocab_id=vocab_id,
                candidates=candidate_out,
                confidence=confidence,
            )
        )

    return TokenResolveResponse(spans=spans)


@router.post("/tokens/action", response_model=TokenActionResponse)
def token_action(
    payload: TokenActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TokenActionResponse:
    ensure_workspace_owner(db, payload.workspace_id)

    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=422, detail="Token cannot be empty")

    if payload.action == "open_word":
        if payload.vocab_id is None:
            raise HTTPException(status_code=422, detail="vocab_id is required for open_word")
        row = db.scalar(
            select(Vocab)
            .options(selectinload(Vocab.lexeme), selectinload(Vocab.mastery))
            .where(Vocab.id == payload.vocab_id)
        )
        if not row or row.workspace_id != payload.workspace_id or row.lexeme is None:
            raise HTTPException(status_code=404, detail="Word not found")
        return TokenActionResponse(
            ok=True,
            destination=f"/words/{row.id}",
            vocab=vocab_out(row),
        )

    if payload.action == "add_to_vocab":
        rows = _load_vocab_rows(db, payload.workspace_id)
        normalized = _normalize(token)
        existing = next((r for r in rows if _matches_vocab(r, normalized)), None)
        if existing is None:
            gloss = (payload.gloss or "").strip()
            workspace = db.get(Workspace, payload.workspace_id)
            language = workspace.language if workspace else payload.language
            lexeme = resolve_lexeme(
                db,
                language,
                surface_form=token,
                gloss_primary=gloss,
            )
            existing = Vocab(
                workspace_id=payload.workspace_id,
                lexeme_id=lexeme.id,
                word=token,
                translation=gloss or lexeme.gloss_primary,
                surface_form=token,
                surface_forms=[token],
                gloss_override=gloss or None,
            )
            sync_legacy_mirrors(existing, lexeme)
            db.add(existing)
            db.flush()
            job = maybe_enqueue_enrichment(
                db, lexeme_id=lexeme.id, vocab_id=existing.id
            )
            db.commit()
            if job is not None:
                background_tasks.add_task(_run_token_enrichment, job.id)
            existing = db.scalar(
                select(Vocab)
                .options(selectinload(Vocab.lexeme), selectinload(Vocab.mastery))
                .where(Vocab.id == existing.id)
            )
        if existing is None or existing.lexeme is None:
            raise HTTPException(status_code=500, detail="Failed to create vocab link")
        return TokenActionResponse(ok=True, vocab=vocab_out(existing))

    # record_occurrence
    vocab_id = payload.vocab_id
    if vocab_id is None:
        normalized = _normalize(token)
        rows = _load_vocab_rows(db, payload.workspace_id)
        matched = next((r for r in rows if _matches_vocab(r, normalized)), None)
        if matched is None:
            raise HTTPException(status_code=422, detail="vocab_id required when token is unknown")
        vocab_id = matched.id

    row = db.get(Vocab, vocab_id)
    if not row or row.workspace_id != payload.workspace_id:
        raise HTTPException(status_code=404, detail="Word not found")

    existing_occ = db.scalar(
        select(WordOccurrence).where(
            WordOccurrence.workspace_id == payload.workspace_id,
            WordOccurrence.vocab_id == vocab_id,
            WordOccurrence.context_type == payload.context_type,
            WordOccurrence.context_id == payload.context_id,
            WordOccurrence.surface_token == token,
            WordOccurrence.char_start == payload.char_start,
        )
    )
    if existing_occ is not None:
        return TokenActionResponse(ok=True, occurrence_id=existing_occ.id)

    occurrence = WordOccurrence(
        workspace_id=payload.workspace_id,
        vocab_id=vocab_id,
        context_type=payload.context_type,
        context_id=payload.context_id,
        surface_token=token,
        char_start=payload.char_start,
        char_end=payload.char_end,
        source=payload.source,
        meta=payload.meta,
    )
    db.add(occurrence)
    db.commit()
    db.refresh(occurrence)
    return TokenActionResponse(ok=True, occurrence_id=occurrence.id)
