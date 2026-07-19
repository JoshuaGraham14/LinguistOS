"""Unit tests for Direction 4 Neurologic clause tracking / beam selection."""

from __future__ import annotations

from research.generation.neurologic_hf import (
    ClauseTracker,
    ScoredHypothesis,
    group_by_gold_fired,
    neurologic_score,
    pick_final_hypothesis,
    prune_irreversible,
    select_diverse_beam,
)


def _tracker(
    *,
    gold: list[list[int]] | None = None,
    negatives: list[list[int]] | None = None,
    ids: list[int] | None = None,
) -> ClauseTracker:
    t = ClauseTracker(
        gold_variants=gold or [[10, 11]],
        negative_variants=negatives or [[20]],
    )
    for token_id in ids or []:
        t.append(token_id)
    return t


def test_clause_tracker_gold_prefix_and_satisfy():
    t = _tracker(gold=[[1, 2, 3]], negatives=[])
    t.append(1)
    assert not t.gold_satisfied
    assert 0.3 < t.prefix_frac < 0.4
    t.append(2)
    assert abs(t.prefix_frac - 2 / 3) < 1e-9
    t.append(3)
    assert t.gold_satisfied
    assert t.prefix_frac == 1.0
    assert t.satisfied_clause_count == 2


def test_clause_tracker_competitor_is_irreversible_fail():
    t = _tracker(gold=[[1]], negatives=[[9, 9]])
    t.append(9)
    assert not t.irreversibly_unsatisfied
    t.append(9)
    assert t.irreversibly_unsatisfied
    assert t.satisfied_clause_count == 0


def test_neurologic_score_rewards_prefix():
    t = _tracker(gold=[[1, 2]], negatives=[], ids=[1])
    assert neurologic_score(-1.0, t, 0.1) == -1.0 + 0.1 * 0.5


def test_prune_drops_irreversible_only():
    ok = ScoredHypothesis(
        token_ids=(1,),
        log_prob=-0.5,
        score=-0.4,
        tracker=_tracker(ids=[1]),
    )
    bad = ScoredHypothesis(
        token_ids=(20,),
        log_prob=-0.1,
        score=0.0,
        tracker=_tracker(ids=[20]),
    )
    assert bad.tracker.irreversibly_unsatisfied
    kept = prune_irreversible([ok, bad])
    assert kept == [ok]


def test_select_diverse_beam_round_robins_groups():
    fired = [
        ScoredHypothesis((1,), -0.1, 1.0, _tracker(gold=[[1]], negatives=[], ids=[1])),
        ScoredHypothesis((2,), -0.2, 0.9, _tracker(gold=[[1]], negatives=[], ids=[1])),
    ]
    unfired = [
        ScoredHypothesis((3,), -0.05, 0.95, _tracker(gold=[[1]], negatives=[], ids=[])),
        ScoredHypothesis((4,), -0.3, 0.5, _tracker(gold=[[1]], negatives=[], ids=[])),
    ]
    selected = select_diverse_beam([*fired, *unfired], num_beams=2)
    assert len(selected) == 2
    groups = group_by_gold_fired(selected)
    assert groups[True] and groups[False]


def test_pick_final_prefers_satisfied_then_likelihood():
    a = ScoredHypothesis(
        (1,),
        -1.0,
        0.0,
        _tracker(gold=[[1]], negatives=[], ids=[1]),
    )
    b = ScoredHypothesis(
        (2,),
        -0.1,
        1.0,
        _tracker(gold=[[1]], negatives=[], ids=[]),
    )
    chosen = pick_final_hypothesis([a, b])
    assert chosen is a
