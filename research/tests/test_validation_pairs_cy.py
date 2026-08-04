"""Structural checks on the Welsh naturalness validation stimuli."""

from __future__ import annotations

from research.evaluation.validation.pairs_loader import (
    CATEGORIES,
    DEFAULT_WELSH_PAIRS_YAML,
    FLAG_VALUES,
    TARGET_FORM_USE_VALUES,
    load_validation_pairs,
)


EXPECTED_PAIR_COUNT = 15
EXPECTED_MIN_PER_CATEGORY = {
    "wrong_construction": 4,
    "agreement": 3,
    "odd_collocation": 2,
    "role_vs_mention": 2,
    "repetition": 1,
    "tense_conflict": 2,
    "rare_but_correct": 1,
}


def test_welsh_pairs_file_exists():
    assert DEFAULT_WELSH_PAIRS_YAML.is_file(), DEFAULT_WELSH_PAIRS_YAML


def test_welsh_pairs_load_and_structure():
    vset = load_validation_pairs(DEFAULT_WELSH_PAIRS_YAML)
    assert vset.prompt_version == "cy-v1"
    assert len(vset) == EXPECTED_PAIR_COUNT

    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    ids: set[str] = set()
    for pair in vset:
        assert pair.pair_id not in ids, f"duplicate pair_id {pair.pair_id}"
        ids.add(pair.pair_id)
        counts[pair.category] += 1

        assert pair.expected_form
        assert pair.lemma
        assert pair.target_language == "cy"
        assert pair.construction in {"synthetic", "periphrastic"}
        assert pair.natural.text
        assert pair.awkward.text
        assert pair.natural.text != pair.awkward.text

        cons = pair.constraints_for("natural")
        assert cons["construction"] == pair.construction
        assert cons["target_language"] == "cy"
        if pair.construction == "periphrastic":
            assert pair.expected_aux, f"{pair.pair_id}: peri needs expected_aux"
            assert cons.get("expected_aux") == pair.expected_aux

        for side_name, sentence in (("natural", pair.natural), ("awkward", pair.awkward)):
            label = sentence.human_label
            for axis in ("grammaticality", "naturalness", "semantic_coherence"):
                v = getattr(label, axis)
                assert 1 <= v <= 5, f"{pair.pair_id}.{side_name}.{axis}={v}"
            assert label.target_form_use in TARGET_FORM_USE_VALUES
            for flag in label.flags:
                assert flag in FLAG_VALUES, f"{pair.pair_id}.{side_name}: bad flag {flag}"

    for category, minimum in EXPECTED_MIN_PER_CATEGORY.items():
        assert counts[category] >= minimum, (
            f"category {category}: {counts[category]} < {minimum}"
        )


def test_welsh_wrong_construction_pairs_flag_both_sides_consistently():
    vset = load_validation_pairs(DEFAULT_WELSH_PAIRS_YAML)
    wc = [p for p in vset if p.category == "wrong_construction"]
    assert len(wc) >= 4
    for pair in wc:
        awkward = pair.awkward.human_label
        assert awkward.target_form_use == "wrong_construction"
        assert "wrong_construction" in awkward.flags
        natural = pair.natural.human_label
        assert natural.target_form_use == "correct_main_verb"


def test_welsh_preferred_side_beats_dispreferred():
    vset = load_validation_pairs(DEFAULT_WELSH_PAIRS_YAML)
    for pair in vset:
        preferred = pair.preferred_sentence.human_label
        dispreferred = pair.dispreferred_sentence.human_label
        axes = ("grammaticality", "naturalness", "semantic_coherence")
        better = [getattr(preferred, a) > getattr(dispreferred, a) for a in axes]
        equal_all = all(
            getattr(preferred, a) == getattr(dispreferred, a) for a in axes
        )
        target_form_diff = preferred.target_form_use != dispreferred.target_form_use
        assert any(better) or (equal_all and target_form_diff), (
            f"{pair.pair_id}: preferred side does not beat dispreferred on any axis "
            "and target_form_use also matches — one of them must differ."
        )
