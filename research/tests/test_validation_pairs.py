"""Structural checks on the committed naturalness validation stimuli."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from research.evaluation.validation.pairs_loader import (
    CATEGORIES,
    DEFAULT_PAIRS_YAML,
    FLAG_VALUES,
    TARGET_FORM_USE_VALUES,
    load_validation_pairs,
)


EXPECTED_PAIR_COUNT = 13
EXPECTED_MIN_PER_CATEGORY = {
    "odd_collocation": 3,
    "agreement": 3,
    "role_vs_mention": 2,
    "repetition": 2,
    "tense_conflict": 2,
    "rare_but_correct": 1,
}


def test_default_pairs_file_exists():
    assert DEFAULT_PAIRS_YAML.is_file(), DEFAULT_PAIRS_YAML


def test_default_pairs_load_and_structure():
    vset = load_validation_pairs()
    assert vset.prompt_version == "v2"
    assert len(vset) == EXPECTED_PAIR_COUNT

    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    ids: set[str] = set()
    for pair in vset:
        assert pair.pair_id not in ids, f"duplicate pair_id {pair.pair_id}"
        ids.add(pair.pair_id)
        counts[pair.category] += 1

        assert pair.expected_form
        assert pair.lemma
        assert pair.natural.text
        assert pair.awkward.text
        assert pair.natural.text != pair.awkward.text

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


def test_preferred_side_beats_dispreferred_on_at_least_one_numeric_axis():
    vset = load_validation_pairs()
    for pair in vset:
        preferred = pair.preferred_sentence.human_label
        dispreferred = pair.dispreferred_sentence.human_label
        axes = ("grammaticality", "naturalness", "semantic_coherence")
        better = [
            getattr(preferred, a) > getattr(dispreferred, a) for a in axes
        ]
        equal_all = all(
            getattr(preferred, a) == getattr(dispreferred, a) for a in axes
        )
        target_form_diff = (
            preferred.target_form_use != dispreferred.target_form_use
        )
        assert any(better) or (equal_all and target_form_diff), (
            f"{pair.pair_id}: preferred side does not beat dispreferred on any axis "
            "and target_form_use also matches — one of them must differ."
        )


def test_loader_rejects_missing_sentences(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent(
            """\
            version: 1
            prompt_version: v1
            pairs:
              - pair_id: bad_1
                category: odd_collocation
                expected_form: come
                lemma: comer
                tense: present
                person: 3rd
                number: singular
                target_language: es
                preferred: natural
                sentences:
                  natural:
                    text: "Ella come una manzana."
                    human_label:
                      grammaticality: 5
                      naturalness: 5
                      semantic_coherence: 5
                      target_form_use: correct_main_verb
                      flags: []
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="natural"):
        load_validation_pairs(bad)


def test_loader_rejects_bad_flag(tmp_path: Path):
    bad = tmp_path / "bad_flag.yaml"
    bad.write_text(
        textwrap.dedent(
            """\
            version: 1
            prompt_version: v1
            pairs:
              - pair_id: bad_flag_1
                category: odd_collocation
                expected_form: come
                lemma: comer
                tense: present
                person: 3rd
                number: singular
                target_language: es
                preferred: natural
                sentences:
                  natural:
                    text: "Ella come una manzana."
                    human_label:
                      grammaticality: 5
                      naturalness: 5
                      semantic_coherence: 5
                      target_form_use: correct_main_verb
                      flags: []
                  awkward:
                    text: "Ella come una puerta."
                    human_label:
                      grammaticality: 5
                      naturalness: 2
                      semantic_coherence: 2
                      target_form_use: correct_main_verb
                      flags: [not_a_real_flag]
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not_a_real_flag"):
        load_validation_pairs(bad)


def test_loader_rejects_duplicate_pair_ids(tmp_path: Path):
    body = textwrap.dedent(
        """\
        version: 1
        prompt_version: v1
        pairs:
          - pair_id: dup_1
            category: odd_collocation
            expected_form: come
            lemma: comer
            tense: present
            person: 3rd
            number: singular
            target_language: es
            preferred: natural
            sentences:
              natural:
                text: "Ella come una manzana."
                human_label:
                  grammaticality: 5
                  naturalness: 5
                  semantic_coherence: 5
                  target_form_use: correct_main_verb
                  flags: []
              awkward:
                text: "Ella come una puerta."
                human_label:
                  grammaticality: 5
                  naturalness: 2
                  semantic_coherence: 2
                  target_form_use: correct_main_verb
                  flags: [odd_collocation]
          - pair_id: dup_1
            category: repetition
            expected_form: come
            lemma: comer
            tense: present
            person: 3rd
            number: singular
            target_language: es
            preferred: natural
            sentences:
              natural:
                text: "Ella come."
                human_label:
                  grammaticality: 5
                  naturalness: 5
                  semantic_coherence: 5
                  target_form_use: correct_main_verb
                  flags: []
              awkward:
                text: "Come come come come."
                human_label:
                  grammaticality: 2
                  naturalness: 1
                  semantic_coherence: 1
                  target_form_use: correct_main_verb
                  flags: [repetition_or_degeneration]
        """
    )
    dup = tmp_path / "dup.yaml"
    dup.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate pair_id"):
        load_validation_pairs(dup)


def test_yaml_is_parseable_standalone():
    with DEFAULT_PAIRS_YAML.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    assert isinstance(raw, dict)
    assert isinstance(raw.get("pairs"), list)
