"""Vocab capture (LOS-401/106) — both legacy and canonical payloads."""

from __future__ import annotations


def test_capture_canonical_only(client, workspace) -> None:
    resp = client.post(
        "/api/vocab",
        json={"workspace_id": workspace["id"], "surface_form": "hablamos"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["surface_form"] == "hablamos"
    assert body["lemma"] == "hablamos"
    assert body["surface_forms"] == ["hablamos"]
    # Legacy mirrors should be populated for backwards compatibility.
    assert body["word"] == "hablamos"
    assert body["translation"] == ""
    assert body["mastery"] is None


def test_capture_legacy_payload_still_works(client, workspace) -> None:
    resp = client.post(
        "/api/vocab",
        json={
            "workspace_id": workspace["id"],
            "word": "perro",
            "translation": "dog",
            "tags": ["noun"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["word"] == "perro"
    assert body["translation"] == "dog"
    assert body["surface_form"] == "perro"
    assert body["lemma"] == "perro"
    assert body["gloss_primary"] == "dog"
    assert body["glosses"] == ["dog"]
    assert body["tags"] == ["noun"]


def test_capture_rejects_empty_payload(client, workspace) -> None:
    resp = client.post(
        "/api/vocab",
        json={"workspace_id": workspace["id"]},
    )
    assert resp.status_code == 422


def test_capture_canonical_with_optional_fields(client, workspace) -> None:
    resp = client.post(
        "/api/vocab",
        json={
            "workspace_id": workspace["id"],
            "surface_form": "casas",
            "lemma": "casa",
            "pos": "noun",
            "cefr": "A1",
            "gloss_primary": "houses",
            "glosses": ["houses", "homes"],
            "notes": "Plural feminine.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lemma"] == "casa"
    assert body["surface_form"] == "casas"
    assert body["pos"] == "noun"
    assert body["cefr"] == "A1"
    assert body["glosses"] == ["houses", "homes"]
    assert body["notes"] == "Plural feminine."


def test_patch_keeps_legacy_and_canonical_in_sync(client, workspace) -> None:
    created = client.post(
        "/api/vocab",
        json={"workspace_id": workspace["id"], "surface_form": "leche"},
    ).json()
    vocab_id = created["id"]

    # Update only the legacy ``word`` -> canonical ``surface_form`` mirrors.
    resp = client.patch(
        f"/api/vocab/{vocab_id}",
        json={"word": "lechita"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["word"] == "lechita"
    assert body["surface_form"] == "lechita"

    # Update only the canonical ``gloss_primary`` -> ``translation`` mirrors.
    resp2 = client.patch(
        f"/api/vocab/{vocab_id}",
        json={"gloss_primary": "little milk"},
    )
    body2 = resp2.json()
    assert body2["gloss_primary"] == "little milk"
    assert body2["translation"] == "little milk"


def test_patch_surface_form_accumulates_surface_forms(client, workspace) -> None:
    created = client.post(
        "/api/vocab",
        json={"workspace_id": workspace["id"], "surface_form": "hablo"},
    ).json()
    vocab_id = created["id"]

    updated = client.patch(
        f"/api/vocab/{vocab_id}",
        json={"surface_form": "hablamos"},
    ).json()
    assert updated["surface_form"] == "hablamos"
    assert "hablo" in updated["surface_forms"]
    assert "hablamos" in updated["surface_forms"]
