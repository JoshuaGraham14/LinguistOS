"""Local-user / workspace ownership helpers shared across routers.

This is intentionally minimal — single-user local dev only. When real
auth lands, every caller of these helpers should keep working as long
as the helpers are reimplemented to derive identity from the request.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, Vocab, Workspace

LOCAL_USER_EMAIL = "local-user@linguistos.local"


def ensure_local_user(db: Session) -> User:
    """Return the single local user, creating it on first call."""
    user = db.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
    if user:
        return user
    user = User(email=LOCAL_USER_EMAIL)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_workspace_owner(db: Session, workspace_id: int) -> Workspace:
    """Return the workspace iff the local user owns it; 404 otherwise."""
    owner = ensure_local_user(db)
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == owner.id,
        )
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def ensure_vocab_owner(db: Session, vocab_id: int) -> Vocab:
    """Return the vocab iff its workspace is owned by the local user."""
    item = db.get(Vocab, vocab_id)
    if not item:
        raise HTTPException(status_code=404, detail="Word not found")
    ensure_workspace_owner(db, item.workspace_id)
    return item
