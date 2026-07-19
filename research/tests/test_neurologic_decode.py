"""Unit tests for Direction 4 Neurologic clause tracking / beam selection."""

from __future__ import annotations

from research.generation.neurologic_hf import (
    ClauseTracker,
    NeurologicHFThinInjectPlainBGenerator,
    NeurologicHFThinPlainBGenerator,
    ScoredHypothesis,
    group_by_gold_fired,
    neurologic_score,
    pick_final_hypothesis,
    prune_irreversible,
    select_diverse_beam,
)
from research.generation import GENERATOR_REGISTRY


def test_registry_adds_neurologic_generators():
    assert "neurologic_hf_thin_plain_b" in GENERATOR_REGISTRY
    assert "neurologic_hf_thin_inject_plain_b" in GENERATOR_REGISTRY
    assert NeurologicHFThinPlainBGenerator._USE_MORPH_BANS is True
    assert NeurologicHFThinPlainBGenerator._MORPH_BAN_MODE == "thin"
    assert NeurologicHFThinPlainBGenerator._USE_SOFT_BIAS is False
    assert NeurologicHFThinPlainBGenerator.USE_HARD_CONSTRAINT is False
    assert NeurologicHFThinInjectPlainBGenerator._INJECT_EXPECTED_FORM is True


def test_neurologic_fix_b_prompt_and_inject():
    plain = NeurologicHFThinPlainBGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    inject = NeurologicHFThinInjectPlainBGenerator(
        model="Qwen/Qwen3-1.7B", temperature=0.0
    )
    constraints = {
        "tense": "present",
        "person": "2nd",
        "number": "singular",
        "expected_form": "buscas",
    }
    plain_prompt = plain._build_user_prompt(
        keyword="buscar",
        translation="to search",
        target_language="es",
        constraints=constraints,
        num_candidates=1,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form=plain._resolve_inject_expected_form(constraints),
    )
    inject_prompt = inject._build_user_prompt(
        keyword="buscar",
        translation="to search",
        target_language="es",
        constraints=constraints,
        num_candidates=1,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form=inject._resolve_inject_expected_form(constraints),
    )
    assert "2–5 words" in plain_prompt
    assert "Required surface form" not in plain_prompt
    assert "Required surface form" in inject_prompt
    assert '"buscas"' in inject_prompt


def test_neurologic_beam_generate_is_not_force_words(monkeypatch):
    calls: list[str] = []

    def fake_neuro(*args, **kwargs):
        calls.append("neurologic")
        return "Buscas el libro."

    monkeypatch.setattr(
        "research.generation.neurologic_hf.neurologic_generate_one",
        fake_neuro,
    )
    gen = NeurologicHFThinPlainBGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    out = gen._beam_generate(
        prompt="Write a sentence.",
        system="You are a tutor.",
        expected_form="buscas",
        morph_ban_set=None,
    )
    assert out == "Buscas el libro."
    assert calls == ["neurologic"]



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
