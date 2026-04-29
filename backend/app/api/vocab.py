from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

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


@router.get("/vocab", response_model=VocabListResponse)
def list_vocab(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> VocabListResponse:
    _ensure_workspace_owner(db, workspace_id)
    items = db.scalars(
        select(Vocab)
        .where(Vocab.workspace_id == workspace_id)
        .order_by(Vocab.created_at.desc())
    ).all()
    return VocabListResponse(items=[VocabOut.model_validate(item) for item in items])


@router.post("/vocab", response_model=VocabOut)
def add_vocab(payload: VocabCreate, db: Session = Depends(get_db)) -> VocabOut:
    _ensure_workspace_owner(db, payload.workspace_id)
    item = Vocab(
        workspace_id=payload.workspace_id,
        word=payload.word.strip(),
        translation=payload.translation.strip(),
        tags=payload.tags,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return VocabOut.model_validate(item)


@router.patch("/vocab/{vocab_id}", response_model=VocabOut)
def update_vocab(vocab_id: int, payload: VocabUpdate, db: Session = Depends(get_db)) -> VocabOut:
    item = db.get(Vocab, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    _ensure_workspace_owner(db, item.workspace_id)
    patch = payload.model_dump(exclude_unset=True)
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
