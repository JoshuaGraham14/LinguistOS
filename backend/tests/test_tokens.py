"""Token endpoint and occurrence persistence tests (MVP+ thin)."""

from __future__ import annotations


def _create_word(client, workspace_id: int, surface: str, translation: str = "") -> int:
    payload = {
        "workspace_id": workspace_id,
        "surface_form": surface,
    }
    if translation:
        payload["translation"] = translation
    resp = client.post(
        "/api/vocab",
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_tokens_resolve_marks_known_and_unknown(client, workspace) -> None:
    wid = workspace["id"]
    vid = _create_word(client, wid, "hablamos")

    resp = client.post(
        "/api/tokens/resolve",
        json={
            "workspace_id": wid,
            "language": "es",
            "text": "Nosotros hablamos bien",
        },
    )
    assert resp.status_code == 200
    spans = resp.json()["spans"]
    habla = next(s for s in spans if s["normalized"] == "hablamos")
    assert habla["vocab_id"] == vid
    unknown = next(s for s in spans if s["normalized"] == "bien")
    assert unknown["vocab_id"] is None


def test_tokens_action_add_to_vocab_creates_word(client, workspace) -> None:
    wid = workspace["id"]
    resp = client.post(
        "/api/tokens/action",
        json={
            "action": "add_to_vocab",
            "workspace_id": wid,
            "language": "es",
            "token": "viajamos",
            "gloss": "we travel",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vocab"]["surface_form"] == "viajamos"


def test_tokens_action_record_occurrence_is_deduped(client, workspace) -> None:
    wid = workspace["id"]
    vid = _create_word(client, wid, "comemos")
    payload = {
        "action": "record_occurrence",
        "workspace_id": wid,
        "language": "es",
        "token": "comemos",
        "vocab_id": vid,
        "context_type": "sentence_practice",
        "context_id": "card-1",
        "char_start": 10,
        "char_end": 17,
    }
    r1 = client.post("/api/tokens/action", json=payload)
    r2 = client.post("/api/tokens/action", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["occurrence_id"] == r2.json()["occurrence_id"]


def test_tokens_action_open_word_destination(client, workspace) -> None:
    wid = workspace["id"]
    vid = _create_word(client, wid, "escribo")
    resp = client.post(
        "/api/tokens/action",
        json={
            "action": "open_word",
            "workspace_id": wid,
            "language": "es",
            "token": "escribo",
            "vocab_id": vid,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["destination"] == f"/words/{vid}"
