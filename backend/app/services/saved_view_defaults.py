"""Default seeded views for a workspace vocabulary database."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SavedView
from app.db.schemas import SavedViewConfig, SavedViewLayout, SortRule

_EMPTY_QUERY: dict = {
    "search": "",
    "tags": [],
    "pos": [],
    "cefr": [],
    "learned": "any",
    "due": "any",
    "boxMin": None,
    "boxMax": None,
    "language": None,
}

_ALL_PROPERTIES = [
    "word",
    "lemma",
    "translation",
    "pos",
    "cefr",
    "tags",
    "box",
    "nextDue",
]


def _config(
    *,
    query: dict | None = None,
    sorts: list[dict] | None = None,
    group_by: str | None = None,
    visible_properties: list[str] | None = None,
    property_order: list[str] | None = None,
) -> dict:
    visible = visible_properties or _ALL_PROPERTIES
    order = property_order or visible
    return SavedViewConfig(
        query=query or _EMPTY_QUERY,
        sorts=[SortRule(**rule) for rule in (sorts or [])],
        groupBy=group_by,
        visibleProperties=visible,
        propertyOrder=order,
    ).model_dump()


DEFAULT_VIEW_SPECS: list[tuple[str, str | None, SavedViewLayout, dict, int]] = [
    (
        "All words",
        "📋",
        "table",
        _config(sorts=[{"field": "word", "direction": "asc"}]),
        0,
    ),
    (
        "Gallery",
        "🖼️",
        "gallery",
        _config(
            sorts=[{"field": "createdAt", "direction": "desc"}],
            visible_properties=["word", "translation", "tags", "learned"],
            property_order=["word", "translation", "tags", "learned"],
        ),
        1,
    ),
    (
        "Review queue",
        "📅",
        "table",
        _config(
            query={
                **_EMPTY_QUERY,
                "learned": "not_learned",
                "due": "due_now",
            },
            sorts=[{"field": "nextDue", "direction": "asc"}],
            visible_properties=["word", "translation", "box", "nextDue", "learned"],
            property_order=["word", "translation", "box", "nextDue", "learned"],
        ),
        2,
    ),
]


def ensure_default_saved_views(db: Session, workspace_id: int) -> list[SavedView]:
    """Create the three default views when a workspace has none."""
    count = db.scalar(
        select(func.count())
        .select_from(SavedView)
        .where(SavedView.workspace_id == workspace_id)
    )
    if count and count > 0:
        return list(
            db.scalars(
                select(SavedView)
                .where(SavedView.workspace_id == workspace_id)
                .order_by(SavedView.position.asc(), SavedView.id.asc())
            ).all()
        )

    created: list[SavedView] = []
    for name, icon, layout, config, position in DEFAULT_VIEW_SPECS:
        view = SavedView(
            workspace_id=workspace_id,
            name=name,
            icon=icon,
            layout=layout,
            config=config,
            position=position,
        )
        db.add(view)
        created.append(view)
    db.commit()
    for view in created:
        db.refresh(view)
    return created
