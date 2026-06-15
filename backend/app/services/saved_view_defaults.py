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
    "statusMatch": "all",
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
    "createdAt",
    "box",
    "nextDue",
]


def default_view_config_for_layout(layout: SavedViewLayout) -> dict:
    """Sensible column defaults when creating a view without explicit config."""
    if layout == "gallery":
        visible = ["word", "translation", "tags", "learned"]
        return _config(
            sorts=[{"field": "createdAt", "direction": "desc"}],
            visible_properties=visible,
            property_order=visible,
        )
    if layout == "board":
        visible = ["word", "translation"]
        return _config(
            sorts=[{"field": "createdAt", "direction": "desc"}],
            group_by="learned",
            visible_properties=visible,
            property_order=visible,
        )
    return _config(sorts=[{"field": "createdAt", "direction": "desc"}])


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
        _config(sorts=[{"field": "createdAt", "direction": "desc"}]),
        0,
    ),
    (
        "Cards",
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
                "statusMatch": "any",
            },
            sorts=[{"field": "nextDue", "direction": "asc"}],
            visible_properties=["word", "translation", "box", "nextDue", "learned"],
            property_order=["word", "translation", "box", "nextDue", "learned"],
        ),
        2,
    ),
]


_ALL_WORDS_SORT = [{"field": "createdAt", "direction": "desc"}]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _is_legacy_all_words_config(config: dict) -> bool:
    sorts = config.get("sorts") or []
    if sorts == [{"field": "word", "direction": "asc"}]:
        return True
    visible = config.get("visibleProperties") or []
    return "createdAt" not in visible and sorts == []


def _is_legacy_review_queue_query(query: dict) -> bool:
    return (
        query.get("learned") == "not_learned"
        and query.get("due") == "due_now"
        and query.get("statusMatch", "all") == "all"
    )


def migrate_review_queue_view_defaults(db: Session, workspace_id: int) -> int:
    """Patch legacy Review queue views to OR learned/due status filters."""
    views = db.scalars(
        select(SavedView).where(
            SavedView.workspace_id == workspace_id,
            SavedView.name == "Review queue",
        )
    ).all()
    updated = 0
    for view in views:
        config = dict(view.config or {})
        query = dict(config.get("query") or {})
        if not _is_legacy_review_queue_query(query):
            continue
        query["statusMatch"] = "any"
        config["query"] = query
        view.config = config
        db.add(view)
        updated += 1
    if updated:
        db.commit()
    return updated


def migrate_gallery_view_name(db: Session, workspace_id: int) -> int:
    """Rename legacy default 'Gallery' views to 'Cards'."""
    views = db.scalars(
        select(SavedView).where(
            SavedView.workspace_id == workspace_id,
            SavedView.name == "Gallery",
            SavedView.layout == "gallery",
        )
    ).all()
    updated = 0
    for view in views:
        view.name = "Cards"
        db.add(view)
        updated += 1
    if updated:
        db.commit()
    return updated


def migrate_all_words_view_defaults(db: Session, workspace_id: int) -> int:
    """Patch legacy 'All words' views to Date Added sort and column."""
    views = db.scalars(
        select(SavedView).where(
            SavedView.workspace_id == workspace_id,
            SavedView.name == "All words",
        )
    ).all()
    updated = 0
    for view in views:
        config = dict(view.config or {})
        if not _is_legacy_all_words_config(config):
            continue
        visible = list(config.get("visibleProperties") or _ALL_PROPERTIES)
        order = list(config.get("propertyOrder") or visible)
        if "createdAt" not in visible:
            insert_at = visible.index("box") if "box" in visible else len(visible)
            visible.insert(insert_at, "createdAt")
        if "createdAt" not in order:
            insert_at = order.index("box") if "box" in order else len(order)
            order.insert(insert_at, "createdAt")
        config["visibleProperties"] = _dedupe_preserve_order(visible)
        config["propertyOrder"] = _dedupe_preserve_order(order)
        config["sorts"] = _ALL_WORDS_SORT
        view.config = config
        db.add(view)
        updated += 1
    if updated:
        db.commit()
    return updated


def migrate_dedupe_view_properties(db: Session, workspace_id: int) -> int:
    """Remove duplicate entries from visibleProperties and propertyOrder."""
    views = db.scalars(
        select(SavedView).where(SavedView.workspace_id == workspace_id)
    ).all()
    updated = 0
    for view in views:
        config = dict(view.config or {})
        visible = _dedupe_preserve_order(list(config.get("visibleProperties") or []))
        order = _dedupe_preserve_order(list(config.get("propertyOrder") or []))
        if visible != config.get("visibleProperties") or order != config.get(
            "propertyOrder"
        ):
            config["visibleProperties"] = visible
            config["propertyOrder"] = order
            view.config = config
            db.add(view)
            updated += 1
    if updated:
        db.commit()
    return updated


def ensure_default_saved_views(db: Session, workspace_id: int) -> list[SavedView]:
    """Create the three default views when a workspace has none."""
    count = db.scalar(
        select(func.count())
        .select_from(SavedView)
        .where(SavedView.workspace_id == workspace_id)
    )
    if count and count > 0:
        migrate_all_words_view_defaults(db, workspace_id)
        migrate_review_queue_view_defaults(db, workspace_id)
        migrate_gallery_view_name(db, workspace_id)
        migrate_dedupe_view_properties(db, workspace_id)
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
