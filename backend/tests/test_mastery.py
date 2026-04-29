"""Per-atom mastery events (LOS-901)."""

from __future__ import annotations


def _create_word(client, workspace_id: int, surface: str = "vivir") -> int:
    resp = client.post(
        "/api/vocab",
        json={"workspace_id": workspace_id, "surface_form": surface},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_get_mastery_returns_zero_state_before_any_event(client, workspace) -> None:
    vid = _create_word(client, workspace["id"])
    resp = client.get(f"/api/vocab/{vid}/mastery")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "strength": 0.0,
        "box": 0,
        "last_reviewed_at": None,
        "next_due": None,
        "streak": 0,
        "failures": 0,
        "successes": 0,
    }


def test_correct_outcome_advances_box_and_strength(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "comer")
    resp = client.post(
        f"/api/vocab/{vid}/mastery/event",
        json={"outcome": "correct"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["box"] == 1
    assert body["streak"] == 1
    assert body["successes"] == 1
    assert body["last_reviewed_at"] is not None
    assert body["next_due"] is not None
    # Strength steps up by 0.2 from zero.
    assert abs(body["strength"] - 0.2) < 1e-9


def test_incorrect_resets_streak_and_decrements_box(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "beber")
    # Two correct, then incorrect.
    client.post(f"/api/vocab/{vid}/mastery/event", json={"outcome": "correct"})
    client.post(f"/api/vocab/{vid}/mastery/event", json={"outcome": "correct"})
    resp = client.post(
        f"/api/vocab/{vid}/mastery/event",
        json={"outcome": "incorrect"},
    )
    body = resp.json()
    assert body["box"] == 1  # 0 -> 1 -> 2 -> 1
    assert body["streak"] == 0
    assert body["successes"] == 2
    assert body["failures"] == 1


def test_skipped_is_a_no_op(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "saltar")
    before = client.get(f"/api/vocab/{vid}/mastery").json()
    client.post(f"/api/vocab/{vid}/mastery/event", json={"outcome": "skipped"})
    after = client.get(f"/api/vocab/{vid}/mastery").json()
    # No mutation is observable from the read API.
    assert before == after


def test_graduated_box_latches_legacy_learned(client, workspace) -> None:
    vid = _create_word(client, workspace["id"], "subir")
    for _ in range(4):
        client.post(f"/api/vocab/{vid}/mastery/event", json={"outcome": "correct"})

    detail = client.get(f"/api/vocab/{vid}").json()
    assert detail["learned"] is True
    assert detail["mastery"]["box"] >= 4
