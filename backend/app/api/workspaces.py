from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, Workspace
from app.db.schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

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


def _serialize(workspace: Workspace) -> WorkspaceOut:
    return WorkspaceOut.model_validate(workspace)


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    owner = _ensure_local_user(db)
    items = db.scalars(
        select(Workspace).where(Workspace.owner_id == owner.id).order_by(Workspace.created_at.asc())
    ).all()
    return [_serialize(item) for item in items]


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> WorkspaceOut:
    owner = _ensure_local_user(db)
    workspace = Workspace(
        owner_id=owner.id,
        name=payload.name.strip(),
        language=payload.language,
        emoji_or_flag=payload.emoji_or_flag.strip() or "🌐",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return _serialize(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def rename_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    owner = _ensure_local_user(db)
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == owner.id,
        )
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace.name = payload.name.strip()
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return _serialize(workspace)
