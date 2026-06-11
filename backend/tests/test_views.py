"""Saved vocabulary database views API."""

from __future__ import annotations


def test_list_views_seeds_defaults(client, workspace) -> None:
    wid = workspace["id"]
    resp = client.get(f"/api/views?workspace_id={wid}")
    assert resp.status_code == 200, resp.text
    views = resp.json()
    assert len(views) == 3
    assert views[0]["name"] == "All words"
    assert views[0]["layout"] == "table"
    assert views[0]["position"] == 0
    assert views[0]["config"]["sorts"] == [
        {"field": "createdAt", "direction": "desc"}
    ]
    assert "createdAt" in views[0]["config"]["visibleProperties"]
    assert views[1]["name"] == "Cards"
    assert views[1]["layout"] == "gallery"
    assert views[2]["name"] == "Review queue"
    assert views[2]["config"]["query"]["due"] == "due_now"
    assert views[2]["config"]["query"]["learned"] == "not_learned"
    assert views[2]["config"]["query"]["statusMatch"] == "any"

    # Second list call should not duplicate seeds.
    again = client.get(f"/api/views?workspace_id={wid}")
    assert len(again.json()) == 3


def test_get_view(client, workspace) -> None:
    listed = client.get(f"/api/views?workspace_id={workspace['id']}").json()
    view_id = listed[0]["id"]
    resp = client.get(f"/api/views/{view_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "All words"


def test_create_update_delete_view(client, workspace) -> None:
    wid = workspace["id"]
    # Seed default views so delete is not blocked as "last view".
    client.get(f"/api/views?workspace_id={wid}")
    create = client.post(
        "/api/views",
        json={
            "workspace_id": wid,
            "name": "Verbs only",
            "layout": "table",
            "config": {
                "query": {
                    "search": "",
                    "tags": ["verb"],
                    "pos": [],
                    "cefr": [],
                    "learned": "any",
                    "due": "any",
                    "statusMatch": "all",
                    "boxMin": None,
                    "boxMax": None,
                    "language": None,
                },
                "sorts": [{"field": "word", "direction": "asc"}],
                "groupBy": None,
                "visibleProperties": ["word", "translation"],
                "propertyOrder": ["word", "translation"],
            },
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["name"] == "Verbs only"
    view_id = body["id"]

    patch = client.patch(
        f"/api/views/{view_id}",
        json={"name": "Verbs", "layout": "board", "config": body["config"]},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["name"] == "Verbs"
    assert patch.json()["layout"] == "board"

    delete = client.delete(f"/api/views/{view_id}")
    assert delete.status_code == 204
    missing = client.get(f"/api/views/{view_id}")
    assert missing.status_code == 404


def test_get_view_not_found(client, workspace) -> None:
    resp = client.get("/api/views/999999")
    assert resp.status_code == 404


def test_create_view_applies_default_columns(client, workspace) -> None:
    wid = workspace["id"]
    create = client.post(
        "/api/views",
        json={
            "workspace_id": wid,
            "name": "Blank",
            "layout": "table",
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert "word" in body["config"]["visibleProperties"]
    assert "createdAt" in body["config"]["visibleProperties"]
    assert body["config"]["sorts"] == [
        {"field": "createdAt", "direction": "desc"}
    ]


def test_delete_last_view_rejected(client, workspace) -> None:
    wid = workspace["id"]
    views = client.get(f"/api/views?workspace_id={wid}").json()
    while len(views) > 1:
        client.delete(f"/api/views/{views[-1]['id']}")
        views = client.get(f"/api/views?workspace_id={wid}").json()

    last_id = views[0]["id"]
    resp = client.delete(f"/api/views/{last_id}")
    assert resp.status_code == 400
    assert client.get(f"/api/views?workspace_id={wid}").json()
