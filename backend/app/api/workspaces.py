from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._auth import ensure_local_user, ensure_workspace_owner
from app.db.database import get_db
from app.db.models import Workspace
from app.db.schemas import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate

router = APIRouter()


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    owner = ensure_local_user(db)
    items = db.scalars(
        select(Workspace)
        .where(Workspace.owner_id == owner.id)
        .order_by(Workspace.created_at.asc())
    ).all()
    return [WorkspaceOut.model_validate(item) for item in items]


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> WorkspaceOut:
    owner = ensure_local_user(db)
    workspace = Workspace(
        owner_id=owner.id,
        name=payload.name.strip(),
        language=payload.language,
        emoji_or_flag=payload.emoji_or_flag.strip() or "🌐",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return WorkspaceOut.model_validate(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def rename_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = ensure_workspace_owner(db, workspace_id)
    workspace.name = payload.name.strip()
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return WorkspaceOut.model_validate(workspace)
