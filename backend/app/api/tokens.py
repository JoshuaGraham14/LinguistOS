"""Token resolution and token actions (MVP+ thin)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._auth import ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Vocab, WordOccurrence
from app.db.schemas import (
    TokenActionRequest,
    TokenActionResponse,
    TokenCandidate,
    TokenResolveRequest,
    TokenResolveResponse,
    TokenSpanOut,
    VocabOut,
)

router = APIRouter()

_TOKEN_RE = re.compile(r"[\w\u00C0-\u017F']+")


def _normalize(token: str) -> str:
    return re.sub(r"[.,!?¿¡;:\"“”()\[\]{}]", "", token.strip().lower())


def _tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for match in _TOKEN_RE.finditer(text):
        out.append((match.group(0), match.start(), match.end()))
    return out


def _matches_vocab(vocab: Vocab, normalized: str) -> bool:
    forms = [vocab.word, vocab.lemma or "", vocab.surface_form or "", *(vocab.surface_forms or [])]
    return any(_normalize(form) == normalized for form in forms if form)


@router.post("/tokens/resolve", response_model=TokenResolveResponse)
def resolve_tokens(
    payload: TokenResolveRequest,
    db: Session = Depends(get_db),
) -> TokenResolveResponse:
    ensure_workspace_owner(db, payload.workspace_id)
    rows = db.scalars(select(Vocab).where(Vocab.workspace_id == payload.workspace_id)).all()

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
                lemma=c.lemma,
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
    db: Session = Depends(get_db),
) -> TokenActionResponse:
    ensure_workspace_owner(db, payload.workspace_id)

    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=422, detail="Token cannot be empty")

    if payload.action == "open_word":
        if payload.vocab_id is None:
            raise HTTPException(status_code=422, detail="vocab_id is required for open_word")
        row = db.get(Vocab, payload.vocab_id)
        if not row or row.workspace_id != payload.workspace_id:
            raise HTTPException(status_code=404, detail="Word not found")
        return TokenActionResponse(ok=True, destination=f"/words/{row.id}", vocab=VocabOut.model_validate(row))

    if payload.action == "add_to_vocab":
        normalized = _normalize(token)
        rows = db.scalars(select(Vocab).where(Vocab.workspace_id == payload.workspace_id)).all()
        existing = next((r for r in rows if _matches_vocab(r, normalized)), None)
        if existing is None:
            gloss = (payload.gloss or "").strip()
            existing = Vocab(
                workspace_id=payload.workspace_id,
                word=token,
                translation=gloss,
                tags=[],
                lemma=token,
                surface_form=token,
                surface_forms=[token],
                gloss_primary=gloss or None,
                glosses=[gloss] if gloss else [],
            )
            db.add(existing)
            db.flush()
            db.commit()
            db.refresh(existing)
        return TokenActionResponse(ok=True, vocab=VocabOut.model_validate(existing))

    # record_occurrence
    vocab_id = payload.vocab_id
    if vocab_id is None:
        normalized = _normalize(token)
        rows = db.scalars(select(Vocab).where(Vocab.workspace_id == payload.workspace_id)).all()
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
