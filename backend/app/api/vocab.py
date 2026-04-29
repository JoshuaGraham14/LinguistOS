from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.db.models import User, Vocab, Workspace
from app.db.schemas import VocabCreate, VocabListResponse, VocabOut, VocabUpdate

router = APIRouter()
LOCAL_USER_EMAIL = "local-user@linguistos.local"


def _ensure_local_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
    if user:
        return user
    user = User(email=LOCAL_USER_EMAIL)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ensure_workspace_owner(db: Session, workspace_id: int) -> Workspace:
    owner = _ensure_local_user(db)
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == owner.id,
        )
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _resolve_capture_fields(payload: VocabCreate) -> tuple[str, str, str, str, list[str]]:
    """Reconcile legacy ``word``/``translation`` and canonical ``surface_form``.

    Returns ``(word, translation, lemma, surface_form, glosses)`` with all
    legacy columns guaranteed populated for backwards compatibility.
    """
    surface = (payload.surface_form or payload.word or "").strip()
    if not surface:
        raise HTTPException(
            status_code=422,
            detail="Either surface_form or word must be provided",
        )
    lemma = (payload.lemma or surface).strip()
    gloss = (payload.gloss_primary or payload.translation or "").strip()
    glosses = list(payload.glosses) if payload.glosses else (
        [gloss] if gloss else []
    )
    return surface, gloss, lemma, surface, glosses


@router.get("/vocab", response_model=VocabListResponse)
def list_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> VocabListResponse:
    _ensure_workspace_owner(db, workspace_id)
    items = db.scalars(
        select(Vocab)
        .options(selectinload(Vocab.mastery))
        .where(Vocab.workspace_id == workspace_id)
        .order_by(Vocab.created_at.desc())
    ).all()
    return VocabListResponse(items=[VocabOut.model_validate(item) for item in items])


@router.get("/vocab/{vocab_id}", response_model=VocabOut)
def get_vocab(vocab_id: int, db: Session = Depends(get_db)) -> VocabOut:
    item = db.scalar(
        select(Vocab)
        .options(selectinload(Vocab.mastery))
        .where(Vocab.id == vocab_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    _ensure_workspace_owner(db, item.workspace_id)
    return VocabOut.model_validate(item)


@router.post("/vocab", response_model=VocabOut)
def add_vocab(payload: VocabCreate, db: Session = Depends(get_db)) -> VocabOut:
    _ensure_workspace_owner(db, payload.workspace_id)
    word, translation, lemma, surface_form, glosses = _resolve_capture_fields(payload)
    item = Vocab(
        workspace_id=payload.workspace_id,
        word=word,
        translation=translation,
        tags=payload.tags,
        lemma=lemma,
        surface_form=surface_form,
        surface_forms=[surface_form],
        gloss_primary=translation or None,
        glosses=glosses,
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


@router.patch("/vocab/{vocab_id}", response_model=VocabOut)
def update_vocab(vocab_id: int, payload: VocabUpdate, db: Session = Depends(get_db)) -> VocabOut:
    item = db.scalar(
        select(Vocab)
        .options(selectinload(Vocab.mastery))
        .where(Vocab.id == vocab_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    _ensure_workspace_owner(db, item.workspace_id)
    patch = payload.model_dump(exclude_unset=True)

    # Keep legacy + canonical fields in sync when only one side is patched.
    if "word" in patch and "surface_form" not in patch:
        patch["surface_form"] = patch["word"]
    if "surface_form" in patch and "word" not in patch:
        patch["word"] = patch["surface_form"]
    if "translation" in patch and "gloss_primary" not in patch:
        patch["gloss_primary"] = patch["translation"]
    if "gloss_primary" in patch and "translation" not in patch:
        patch["translation"] = patch["gloss_primary"]

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
    _ensure_workspace_owner(db, item.workspace_id)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.delete("/vocab")
def clear_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _ensure_workspace_owner(db, workspace_id)
    items = db.scalars(select(Vocab).where(Vocab.workspace_id == workspace_id)).all()
    for item in items:
        db.delete(item)
    db.commit()
    return {"ok": True}
