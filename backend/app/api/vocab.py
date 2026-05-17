from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api._auth import ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Vocab
from app.db.schemas import VocabCreate, VocabListResponse, VocabOut, VocabUpdate

router = APIRouter()


def _capitalize_first_word(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[0].upper() + stripped[1:]


class _ResolvedCapture:
    """Resolved capture fields, with legacy + canonical guaranteed populated."""

    __slots__ = ("word", "translation", "lemma", "surface_form", "glosses")

    def __init__(self, payload: VocabCreate) -> None:
        surface = _capitalize_first_word(payload.surface_form or payload.word or "")
        if not surface:
            raise HTTPException(
                status_code=422,
                detail="Either surface_form or word must be provided",
            )
        gloss = (payload.gloss_primary or payload.translation or "").strip()
        self.surface_form = surface
        self.word = surface
        self.lemma = _capitalize_first_word(payload.lemma or surface)
        self.translation = gloss
        if payload.glosses:
            self.glosses = list(payload.glosses)
        elif gloss:
            self.glosses = [gloss]
        else:
            self.glosses = []


def _load_vocab_with_mastery(db: Session, vocab_id: int) -> Vocab | None:
    return db.scalar(
        select(Vocab)
        .options(selectinload(Vocab.mastery))
        .where(Vocab.id == vocab_id)
    )


@router.get("/vocab", response_model=VocabListResponse)
def list_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> VocabListResponse:
    ensure_workspace_owner(db, workspace_id)
    items = db.scalars(
        select(Vocab)
        .options(selectinload(Vocab.mastery))
        .where(Vocab.workspace_id == workspace_id)
        .order_by(Vocab.created_at.desc())
    ).all()
    return VocabListResponse(items=[VocabOut.model_validate(item) for item in items])


@router.get("/vocab/{vocab_id}", response_model=VocabOut)
def get_vocab(vocab_id: int, db: Session = Depends(get_db)) -> VocabOut:
    item = _load_vocab_with_mastery(db, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    return VocabOut.model_validate(item)


@router.post("/vocab", response_model=VocabOut)
def add_vocab(payload: VocabCreate, db: Session = Depends(get_db)) -> VocabOut:
    ensure_workspace_owner(db, payload.workspace_id)
    capture = _ResolvedCapture(payload)
    item = Vocab(
        workspace_id=payload.workspace_id,
        word=capture.word,
        translation=capture.translation,
        tags=payload.tags,
        lemma=capture.lemma,
        surface_form=capture.surface_form,
        surface_forms=[capture.surface_form],
        gloss_primary=capture.translation or None,
        glosses=capture.glosses,
        pos=payload.pos,
        cefr=payload.cefr,
        frequency_rank=payload.frequency_rank,
        gender=payload.gender,
        conjugation_class=payload.conjugation_class,
        morph_features=payload.morph_features,
        ipa=payload.ipa,
        audio_url=payload.audio_url,
        image_url=payload.image_url,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return VocabOut.model_validate(item)


# Fields that, when patched, must be mirrored to keep legacy and canonical
# columns in sync until the legacy adapter retires.
_PATCH_MIRRORS: tuple[tuple[str, str], ...] = (
    ("word", "surface_form"),
    ("translation", "gloss_primary"),
)


@router.patch("/vocab/{vocab_id}", response_model=VocabOut)
def update_vocab(vocab_id: int, payload: VocabUpdate, db: Session = Depends(get_db)) -> VocabOut:
    item = _load_vocab_with_mastery(db, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    patch = payload.model_dump(exclude_unset=True)

    for legacy, canonical in _PATCH_MIRRORS:
        if legacy in patch and canonical not in patch:
            patch[canonical] = patch[legacy]
        elif canonical in patch and legacy not in patch:
            patch[legacy] = patch[canonical]

    for field in ("word", "surface_form", "lemma"):
        value = patch.get(field)
        if isinstance(value, str):
            patch[field] = _capitalize_first_word(value)

    # Keep the "forms seen" history accumulating as the displayed surface
    # changes over time (Word Home depends on this list).
    patched_surface = patch.get("surface_form")
    if isinstance(patched_surface, str):
        normalized = patched_surface.strip()
        if normalized:
            forms = list(item.surface_forms or [])
            if normalized not in forms:
                forms.append(normalized)
                patch["surface_forms"] = forms

    for field, value in patch.items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return VocabOut.model_validate(item)


@router.delete("/vocab/{vocab_id}")
def delete_vocab(vocab_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    item = db.get(Vocab, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.delete("/vocab")
def clear_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    ensure_workspace_owner(db, workspace_id)
    items = db.scalars(select(Vocab).where(Vocab.workspace_id == workspace_id)).all()
    for item in items:
        db.delete(item)
    db.commit()
    return {"ok": True}
