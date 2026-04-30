"""Sentence persistence and word-link cascades (LOS-501)."""

from __future__ import annotations


def _create_word(client, workspace_id: int, surface: str) -> int:
    resp = client.post(
        "/api/vocab",
        json={"workspace_id": workspace_id, "surface_form": surface},
    )
    return resp.json()["id"]


def test_create_and_list_sentence(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "comemos")
    resp = client.post(
        "/api/sentences",
        json={
            "workspace_id": workspace["id"],
            "text": "Comemos pan en casa.",
            "translation": "We eat bread at home.",
            "language": "es",
            "links": [
                {
                    "vocab_id": vid,
                    "surface_token": "Comemos",
                    "position": 0,
                    "role": "target",
                }
            ],
        },
    )
    assert resp.status_code == 200
    sentence = resp.json()
    assert sentence["text"].startswith("Comemos")
    assert len(sentence["links"]) == 1
    assert sentence["links"][0]["vocab_id"] == vid

    listing = client.get(f"/api/sentences?workspace_id={workspace['id']}")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(s["id"] == sentence["id"] for s in items)


def test_create_rejects_link_to_other_workspace(client, workspace) -> None:
    other = client.post(
        "/api/workspaces",
        json={"name": "Other", "language": "es", "emoji_or_flag": "🌐"},
    ).json()
    foreign_vid = _create_word(client, other["id"], "extranjero")

    resp = client.post(
        "/api/sentences",
        json={
            "workspace_id": workspace["id"],
            "text": "Foreign vocab linked.",
            "language": "es",
            "links": [
                {
                    "vocab_id": foreign_vid,
                    "surface_token": "Foreign",
                    "position": 0,
                }
            ],
        },
    )
    assert resp.status_code == 422


def test_filter_sentences_by_vocab(client, workspace) -> None:
    a = _create_word(client, workspace["id"], "agua")
    b = _create_word(client, workspace["id"], "fuego")
    s_a = client.post(
        "/api/sentences",
        json={
            "workspace_id": workspace["id"],
            "text": "Bebo agua.",
            "language": "es",
            "links": [
                {"vocab_id": a, "surface_token": "agua", "position": 1}
            ],
        },
    ).json()
    s_b = client.post(
        "/api/sentences",
        json={
            "workspace_id": workspace["id"],
            "text": "Veo fuego.",
            "language": "es",
            "links": [
                {"vocab_id": b, "surface_token": "fuego", "position": 1}
            ],
        },
    ).json()

    listing = client.get(
        f"/api/sentences?workspace_id={workspace['id']}&vocab_id={a}"
    )
    items = listing.json()["items"]
    ids = [s["id"] for s in items]
    assert s_a["id"] in ids
    assert s_b["id"] not in ids


def test_deleting_vocab_cascades_to_sentence_links(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "borrar")
    sentence = client.post(
        "/api/sentences",
        json={
            "workspace_id": workspace["id"],
            "text": "Vamos a borrar esto.",
            "language": "es",
            "links": [
                {"vocab_id": vid, "surface_token": "borrar", "position": 2}
            ],
        },
    ).json()

    # Delete the vocab; the sentence row should remain but the link should
    # be cascaded away by the FK ondelete=CASCADE.
    resp = client.delete(f"/api/vocab/{vid}")
    assert resp.status_code == 200

    refreshed = client.get(f"/api/sentences/{sentence['id']}").json()
    assert refreshed["links"] == []
