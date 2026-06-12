"""Vocabulary suggestion and selected-candidate enrichment."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def force_vocab_suggest_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import vocab_suggest

    monkeypatch.setattr(vocab_suggest, "_call_openai_json", lambda *_args, **_kwargs: None)


def test_suggest_returns_direct_candidates_only(client, workspace) -> None:
    resp = client.post(
        "/api/vocab/suggest",
        json={
            "workspace_id": workspace["id"],
            "input_text": "to play",
            "direction": "en-to-target",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mock"] is True
    assert body["candidates"] == [
        {"text": "jugar", "pos": "verb", "context": "to play a game or sport"},
        {"text": "tocar", "pos": "verb", "context": "to play an instrument"},
    ]


def test_suggest_handles_target_to_english(client, workspace) -> None:
    resp = client.post(
        "/api/vocab/suggest",
        json={
            "workspace_id": workspace["id"],
            "input_text": "tocar",
            "direction": "target-to-en",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"] == [
        {"text": "to touch", "pos": "verb", "context": "to make physical contact"},
        {"text": "to play music", "pos": "verb", "context": "to play an instrument"},
    ]


def test_suggest_swaps_when_english_is_in_target_field(client, workspace) -> None:
    resp = client.post(
        "/api/vocab/suggest",
        json={
            "workspace_id": workspace["id"],
            "input_text": "hello",
            "direction": "target-to-en",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mock"] is True
    assert body["field_swap"] is True
    assert body["resolved_direction"] == "en-to-target"
    assert body["candidates"] == [
        {"text": "hola", "pos": "other", "context": "a greeting"},
    ]


def test_suggest_swaps_when_target_is_in_english_field(client, workspace) -> None:
    resp = client.post(
        "/api/vocab/suggest",
        json={
            "workspace_id": workspace["id"],
            "input_text": "hola",
            "direction": "en-to-target",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["field_swap"] is True
    assert body["resolved_direction"] == "target-to-en"
    assert body["candidates"] == [
        {"text": "hello", "pos": "other", "context": "a greeting"},
    ]


def test_enrich_prepares_selected_pair_for_save(client, workspace) -> None:
    resp = client.post(
        "/api/vocab/suggest/enrich",
        json={
            "workspace_id": workspace["id"],
            "input_text": "to eat",
            "selected_text": "comer",
            "direction": "en-to-target",
            "pos": "verb",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mock"] is True
    assert body["draft"]["surface_form"] == "comer"
    assert body["draft"]["lemma"] == "comer"
    assert body["draft"]["gloss_primary"] == "to eat"
    assert body["draft"]["tags"] == ["verb"]
