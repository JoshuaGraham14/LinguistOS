from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api._auth import ensure_workspace_owner
from app.db.database import get_db
from app.db.models import SavedView
from app.db.schemas import SavedViewCreate, SavedViewOut, SavedViewUpdate
from app.services.saved_view_defaults import ensure_default_saved_views

router = APIRouter()


def _get_owned_view(db: Session, view_id: int) -> SavedView:
    view = db.get(SavedView, view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View not found.")
    ensure_workspace_owner(db, view.workspace_id)
    return view


def _to_out(view: SavedView) -> SavedViewOut:
    return SavedViewOut.model_validate(view)


@router.get("/views", response_model=list[SavedViewOut])
def list_views(
    workspace_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> list[SavedViewOut]:
    ensure_workspace_owner(db, workspace_id)
    views = ensure_default_saved_views(db, workspace_id)
    return [_to_out(view) for view in views]


@router.get("/views/{view_id}", response_model=SavedViewOut)
def get_view(view_id: int, db: Session = Depends(get_db)) -> SavedViewOut:
    view = _get_owned_view(db, view_id)
    return _to_out(view)


@router.post("/views", response_model=SavedViewOut)
def create_view(payload: SavedViewCreate, db: Session = Depends(get_db)) -> SavedViewOut:
    ensure_workspace_owner(db, payload.workspace_id)
    position = payload.position
    if position is None:
        max_pos = db.scalar(
            select(func.max(SavedView.position)).where(
                SavedView.workspace_id == payload.workspace_id
            )
        )
        position = (max_pos or -1) + 1

    view = SavedView(
        workspace_id=payload.workspace_id,
        name=payload.name.strip(),
        icon=payload.icon,
        layout=payload.layout,
        config=payload.config.model_dump(),
        position=position,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return _to_out(view)


@router.patch("/views/{view_id}", response_model=SavedViewOut)
def update_view(
    view_id: int,
    payload: SavedViewUpdate,
    db: Session = Depends(get_db),
) -> SavedViewOut:
    view = _get_owned_view(db, view_id)
    if payload.name is not None:
        view.name = payload.name.strip()
    if payload.icon is not None:
        view.icon = payload.icon or None
    if payload.layout is not None:
        view.layout = payload.layout
    if payload.config is not None:
        view.config = payload.config.model_dump()
    if payload.position is not None:
        view.position = payload.position
    db.add(view)
    db.commit()
    db.refresh(view)
    return _to_out(view)


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(view_id: int, db: Session = Depends(get_db)) -> Response:
    view = _get_owned_view(db, view_id)
    db.delete(view)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
