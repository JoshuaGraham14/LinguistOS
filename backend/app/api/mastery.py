"""Per-atom mastery events and reads (LOS-901).

Mastery is the single source of truth for review state across flashcards,
sentences, and any future review surface. The rule set is a deterministic
Leitner-style schedule chosen for transparency; SM-2/FSRS can replace it
in a follow-up without changing the API surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Vocab, Workspace, WordMastery
from app.db.schemas import MasteryEvent, MasteryOut

router = APIRouter()

# Box -> days until next review.
_LEITNER_INTERVALS_DAYS = [1, 2, 4, 8, 16, 30]


def _ensure_mastery(db: Session, vocab: Vocab) -> WordMastery:
    if vocab.mastery is not None:
        return vocab.mastery
    mastery = WordMastery(workspace_id=vocab.workspace_id, vocab_id=vocab.id)
    db.add(mastery)
    db.flush()
    return mastery


def _apply_outcome(mastery: WordMastery, outcome: str) -> None:
    now = datetime.utcnow()
    mastery.last_reviewed_at = now

    if outcome == "correct":
        mastery.strength = min(1.0, mastery.strength + 0.2)
        mastery.box = min(5, mastery.box + 1)
        mastery.streak += 1
        mastery.successes += 1
    elif outcome == "incorrect":
        mastery.strength = max(0.0, mastery.strength - 0.3)
        mastery.box = max(0, mastery.box - 1)
        mastery.streak = 0
        mastery.failures += 1
    elif outcome == "hinted":
        mastery.strength = min(1.0, mastery.strength + 0.05)
    elif outcome == "skipped":
        # No-op for strength/box; we still record the timestamp above.
        pass

    interval_days = _LEITNER_INTERVALS_DAYS[
        min(mastery.box, len(_LEITNER_INTERVALS_DAYS) - 1)
    ]
    mastery.next_due = now + timedelta(days=interval_days)


def _get_vocab_or_404(db: Session, vocab_id: int) -> Vocab:
    item = db.get(Vocab, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    workspace = db.get(Workspace, item.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return item


@router.post("/vocab/{vocab_id}/mastery/event", response_model=MasteryOut)
def record_mastery_event(
    vocab_id: int,
    payload: MasteryEvent,
    db: Session = Depends(get_db),
) -> MasteryOut:
    vocab = _get_vocab_or_404(db, vocab_id)
    mastery = _ensure_mastery(db, vocab)
    _apply_outcome(mastery, payload.outcome)

    # Keep legacy ``learned`` boolean roughly in sync with mastery box.
    vocab.learned = mastery.box >= 4 or vocab.learned

    db.add(mastery)
    db.add(vocab)
    db.commit()
    db.refresh(mastery)
    return MasteryOut.model_validate(mastery)


@router.get("/vocab/{vocab_id}/mastery", response_model=MasteryOut)
def get_mastery(vocab_id: int, db: Session = Depends(get_db)) -> MasteryOut:
    vocab = _get_vocab_or_404(db, vocab_id)
    mastery = vocab.mastery
    if mastery is None:
        # Return a default zero-state without persisting anything.
        return MasteryOut(
            strength=0.0,
            box=0,
            last_reviewed_at=None,
            next_due=None,
            streak=0,
            failures=0,
            successes=0,
        )
    return MasteryOut.model_validate(mastery)
