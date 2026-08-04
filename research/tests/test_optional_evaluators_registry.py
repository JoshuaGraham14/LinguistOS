"""Tests for the optional-evaluator registry and pipeline merge behaviour."""

from __future__ import annotations

import pytest

from research.evaluation.sentence import (
    DEFAULT_EVALUATORS,
    OPTIONAL_EVALUATORS,
    build_optional_evaluators,
)
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.cysill import EVALUATOR_NAME as CYSILL_NAME
from research.evaluation.sentence.fluency_perplexity import (
    EVALUATOR_NAME as PPL_EVALUATOR_NAME,
    FluencyPerplexityEvaluator,
)
from research.evaluation.sentence.naturalness_llm_judge import (
    EVALUATOR_NAME as JUDGE_EVALUATOR_NAME,
    NaturalnessLlmJudgeEvaluator,
)
from research.pipeline import _merge_evaluators


class _Dummy(BaseEvaluator):
    def __init__(self, name_: str) -> None:
        self._n = name_

    @property
    def name(self) -> str:
        return self._n

    def evaluate(self, sentence, translation, constraints):
        return EvaluationResult(score=1.0)


def test_registry_contains_expected_evaluators():
    assert set(OPTIONAL_EVALUATORS) == {
        PPL_EVALUATOR_NAME,
        JUDGE_EVALUATOR_NAME,
        CYSILL_NAME,
    }


def test_defaults_do_not_include_optionals():
    names = {ev.name for ev in DEFAULT_EVALUATORS}
    assert PPL_EVALUATOR_NAME not in names
    assert JUDGE_EVALUATOR_NAME not in names
    assert CYSILL_NAME not in names


def test_build_optional_evaluators_by_name():
    evs = build_optional_evaluators(
        [PPL_EVALUATOR_NAME, JUDGE_EVALUATOR_NAME]
    )
    assert [ev.name for ev in evs] == [PPL_EVALUATOR_NAME, JUDGE_EVALUATOR_NAME]
    assert isinstance(evs[0], FluencyPerplexityEvaluator)
    assert isinstance(evs[1], NaturalnessLlmJudgeEvaluator)


def test_build_optional_evaluators_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown optional evaluator"):
        build_optional_evaluators(["not_a_real_evaluator"])


def test_build_optional_evaluators_empty_returns_empty():
    assert build_optional_evaluators([]) == []


def test_merge_evaluators_none_extras_returns_defaults_copy():
    merged = _merge_evaluators(DEFAULT_EVALUATORS, None)
    assert merged is not DEFAULT_EVALUATORS
    assert [ev.name for ev in merged] == [ev.name for ev in DEFAULT_EVALUATORS]


def test_merge_evaluators_appends_new_evaluators_in_order():
    extra = [_Dummy("z_extra_1"), _Dummy("z_extra_2")]
    merged = _merge_evaluators(DEFAULT_EVALUATORS, extra)
    assert [ev.name for ev in merged[: len(DEFAULT_EVALUATORS)]] == [
        ev.name for ev in DEFAULT_EVALUATORS
    ]
    assert [ev.name for ev in merged[len(DEFAULT_EVALUATORS):]] == [
        "z_extra_1",
        "z_extra_2",
    ]


def test_merge_evaluators_dedupes_by_name():
    default_name = DEFAULT_EVALUATORS[0].name
    duplicate = _Dummy(default_name)
    extra_unique = _Dummy("z_extra_unique")
    merged = _merge_evaluators(DEFAULT_EVALUATORS, [duplicate, extra_unique])
    # Duplicate silently dropped; unique appended.
    names = [ev.name for ev in merged]
    assert names.count(default_name) == 1
    assert names[-1] == "z_extra_unique"
