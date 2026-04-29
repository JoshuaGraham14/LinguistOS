"""Per-atom mastery events and reads (LOS-901).

Mastery is the single source of truth for review state across flashcards,
sentences, and any future review surface. The rule set is a deterministic
Leitner-style schedule chosen for transparency; SM-2/FSRS can replace it
in a follow-up without changing the API surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api._auth import ensure_vocab_owner
from app.db.database import get_db
from app.db.models import Vocab, WordMastery
from app.db.schemas import MasteryEvent, MasteryOut

router = APIRouter()

# Box -> days until next review.
_LEITNER_INTERVALS_DAYS = [1, 2, 4, 8, 16, 30]
_GRADUATED_BOX = 4


def _ensure_mastery(db: Session, vocab: Vocab) -> WordMastery:
    if vocab.mastery is not None:
        return vocab.mastery
    mastery = WordMastery(workspace_id=vocab.workspace_id, vocab_id=vocab.id)
    db.add(mastery)
    db.flush()
    return mastery


def _apply_outcome(mastery: WordMastery, outcome: str) -> None:
    """Apply a review outcome, mutating the mastery row in place.

    Semantics:
    - ``correct``: +0.20 strength, +1 box (cap 5), streak +1.
    - ``incorrect``: -0.30 strength, -1 box (floor 0), streak reset.
    - ``hinted``: +0.05 strength only; box and next_due unchanged so a
      hinted answer doesn't disguise a half-learned word as scheduled.
    - ``skipped``: pure no-op (no last_reviewed_at, no next_due bump);
      skipped cards re-surface immediately on the next deck pass.
    """
    if outcome == "skipped":
        return

    now = datetime.utcnow()
    mastery.last_reviewed_at = now
    box_changed = False

    if outcome == "correct":
        mastery.strength = min(1.0, mastery.strength + 0.2)
        mastery.box = min(5, mastery.box + 1)
        mastery.streak += 1
        mastery.successes += 1
        box_changed = True
    elif outcome == "incorrect":
        mastery.strength = max(0.0, mastery.strength - 0.3)
        mastery.box = max(0, mastery.box - 1)
        mastery.streak = 0
        mastery.failures += 1
        box_changed = True
    elif outcome == "hinted":
        mastery.strength = min(1.0, mastery.strength + 0.05)

    if box_changed:
        interval_days = _LEITNER_INTERVALS_DAYS[
            min(mastery.box, len(_LEITNER_INTERVALS_DAYS) - 1)
        ]
        mastery.next_due = now + timedelta(days=interval_days)


@router.post("/vocab/{vocab_id}/mastery/event", response_model=MasteryOut)
def record_mastery_event(
    vocab_id: int,
    payload: MasteryEvent,
    db: Session = Depends(get_db),
) -> MasteryOut:
    vocab = ensure_vocab_owner(db, vocab_id)
    mastery = _ensure_mastery(db, vocab)
    _apply_outcome(mastery, payload.outcome)

    # Once a word reaches the graduated box, the legacy ``learned`` flag
    # latches true. We don't unset it on regression because users tend
    # to read ``learned`` as "I've recognised this word at least once".
    if mastery.box >= _GRADUATED_BOX:
        vocab.learned = True

    db.add(mastery)
    db.add(vocab)
    db.commit()
    db.refresh(mastery)
    return MasteryOut.model_validate(mastery)


@router.get("/vocab/{vocab_id}/mastery", response_model=MasteryOut)
def get_mastery(vocab_id: int, db: Session = Depends(get_db)) -> MasteryOut:
    vocab = ensure_vocab_owner(db, vocab_id)
    mastery = vocab.mastery
    if mastery is None:
        # Default zero-state response; we don't persist a row until the
        # learner actually reviews this word.
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
