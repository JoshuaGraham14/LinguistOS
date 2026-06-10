"""Integration checks for shared lexeme deduplication."""

from __future__ import annotations


def test_two_workspaces_share_lexeme_for_same_word(client) -> None:
    ws1 = client.post(
        "/api/workspaces",
        json={"name": "Dedup A", "language": "es", "emoji_or_flag": "A"},
    ).json()
    ws2 = client.post(
        "/api/workspaces",
        json={"name": "Dedup B", "language": "es", "emoji_or_flag": "B"},
    ).json()

    v1 = client.post(
        "/api/vocab",
        json={
            "workspace_id": ws1["id"],
            "word": "gato",
            "translation": "cat",
            "tags": ["noun"],
        },
    ).json()
    v2 = client.post(
        "/api/vocab",
        json={
            "workspace_id": ws2["id"],
            "word": "gato",
            "translation": "cat",
            "tags": ["noun"],
        },
    ).json()

    assert v1["lexeme_id"] == v2["lexeme_id"]
    assert v1["id"] != v2["id"]
