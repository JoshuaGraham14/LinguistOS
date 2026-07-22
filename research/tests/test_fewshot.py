"""Tests for Direction 5 few-shot exemplar selection and prompt assembly."""

from __future__ import annotations

from research.generation.fewshot import (
    format_demonstration_block,
    load_exemplar_pool,
    select_dynamic,
    select_exemplars,
    select_static,
)
from research.generation.fewshot_hf import (
    FewShotDynamicHFGenerator,
    FewShotStaticHFGenerator,
)

# smoke5 test verbs — exemplars must never include these (leakage guard).
SMOKE5_VERBS = {"buscar", "cercar", "desplazar", "esperanzar", "fincar"}


def test_pool_loads_and_is_disjoint_from_smoke5():
    pool = load_exemplar_pool()
    assert len(pool) >= 30
    verbs = {ex.verb for ex in pool}
    assert verbs.isdisjoint(SMOKE5_VERBS)
    # Every indicative tense has at least K=3 exemplars for dynamic fill.
    for tense in ("present", "preterite", "imperfect", "future", "conditional"):
        assert sum(ex.tense == tense for ex in pool) >= 3


def test_static_is_deterministic_and_spans_tenses():
    pool = load_exemplar_pool()
    first = select_static(pool, 3)
    second = select_static(pool, 3)
    assert [e.expected_form for e in first] == [e.expected_form for e in second]
    assert len(first) == 3
    # Round-robin across tenses => 3 distinct tenses for K=3.
    assert len({e.tense for e in first}) == 3


def test_dynamic_matches_target_tense():
    pool = load_exemplar_pool()
    picked = select_dynamic(pool, {"tense": "conditional"}, 3)
    assert len(picked) == 3
    assert all(e.tense == "conditional" for e in picked)


def test_dynamic_backfills_when_tense_pool_short():
    pool = load_exemplar_pool()
    # participle has only 4 exemplars; K=8 forces back-fill from other tenses.
    picked = select_dynamic(pool, {"tense": "participle"}, 8)
    assert len(picked) == 8
    assert picked[0].tense == "participle"
    assert any(e.tense != "participle" for e in picked)


def test_dynamic_excludes_target_verb():
    pool = load_exemplar_pool()
    picked = select_dynamic(
        pool, {"tense": "present"}, 3, exclude_verb="hablar"
    )
    assert all(e.verb != "hablar" for e in picked)


def test_select_exemplars_dispatch_and_bad_mode():
    pool = load_exemplar_pool()
    assert select_exemplars(pool, "static", 2)
    assert select_exemplars(pool, "dynamic", 2, constraints={"tense": "future"})
    try:
        select_exemplars(pool, "nonsense", 2)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown mode")


def test_format_block_contains_sentences_and_marker():
    pool = load_exemplar_pool()
    picked = select_dynamic(pool, {"tense": "future"}, 3)
    block = format_demonstration_block(picked)
    assert "Example 1" in block
    assert picked[0].sentence in block
    assert block.strip().endswith("---")


def test_format_block_empty_for_no_exemplars():
    assert format_demonstration_block([]) == ""


def test_generator_prepends_block_and_hides_target_verb():
    gen = FewShotDynamicHFGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    constraints = {
        "tense": "conditional",
        "person": "1st",
        "number": "plural",
        "expected_form": "cercaríamos",
    }
    prompt = gen._build_user_prompt(
        keyword="cercar",
        translation="cercar",
        target_language="es",
        constraints=constraints,
        num_candidates=1,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form=None,
    )
    assert "Study these worked examples" in prompt
    # Demonstrations must be tense-matched conditional exemplars...
    assert "conditional tense" in prompt
    # ...and must never reveal the target verb's own form.
    assert "cercar" not in prompt.split("---")[0]


def test_static_generator_block_is_cell_invariant():
    gen = FewShotStaticHFGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    kwargs = dict(
        translation="x",
        target_language="es",
        num_candidates=1,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form=None,
    )
    block_a = gen._fewshot_block({"tense": "present"}, "hablarx")
    block_b = gen._fewshot_block({"tense": "future"}, "hablarx")
    # Static demonstrations do not depend on the target cell's tense.
    assert block_a == block_b
    del kwargs  # only exercised indirectly; kept for clarity
