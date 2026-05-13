"""Tests for evaluation framework: BaseEvaluator ABC, GrammarEvaluator stub."""

from __future__ import annotations

import pytest

from research.evaluation.base import BaseEvaluator, EvaluationResult
from research.evaluation.grammar import GrammarEvaluator


# ── EvaluationResult ─────────────────────────────────────────────────────────


def test_evaluation_result_defaults():
    r = EvaluationResult(score=0.75)
    assert r.score == 0.75
    assert r.details is None


def test_evaluation_result_with_details():
    r = EvaluationResult(score=1.0, details={"check": True})
    assert r.details == {"check": True}


# ── BaseEvaluator ABC ────────────────────────────────────────────────────────


def test_cannot_instantiate_base_evaluator():
    with pytest.raises(TypeError):
        BaseEvaluator()


def test_concrete_subclass_must_implement_name_and_evaluate():
    class Incomplete(BaseEvaluator):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_concrete_subclass_works():
    class AlwaysOne(BaseEvaluator):
        @property
        def name(self) -> str:
            return "always_one"

        def evaluate(self, sentence, translation, constraints):
            return EvaluationResult(score=1.0)

    e = AlwaysOne()
    assert e.name == "always_one"
    result = e.evaluate("Hola.", "Hello.", {})
    assert result.score == 1.0


# ── GrammarEvaluator (stub) ─────────────────────────────────────────────────

CONSTRAINTS = {
    "keyword": "comer",
    "translation": "to eat",
    "tense": "past",
    "person": "1st",
    "number": "plural",
    "target_language": "es",
}


def test_grammar_evaluator_name():
    assert GrammarEvaluator().name == "grammar_stub"


def test_grammar_evaluator_perfect_sentence():
    result = GrammarEvaluator().evaluate(
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 1.0
    assert result.details["has_keyword_stem"] is True
    assert result.details["has_translation"] is True
    assert result.details["is_nonempty"] is True


def test_grammar_evaluator_missing_keyword():
    result = GrammarEvaluator().evaluate(
        sentence="Nosotros hablamos español.",
        translation="We spoke Spanish.",
        constraints=CONSTRAINTS,
    )
    assert result.details["has_keyword_stem"] is False
    assert result.score < 1.0


def test_grammar_evaluator_empty_sentence():
    result = GrammarEvaluator().evaluate(
        sentence="",
        translation="We ate pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.details["is_nonempty"] is False
    assert result.details["has_keyword_stem"] is False


def test_grammar_evaluator_empty_translation():
    result = GrammarEvaluator().evaluate(
        sentence="Nosotros comimos pizza.",
        translation="",
        constraints=CONSTRAINTS,
    )
    assert result.details["has_translation"] is False
    assert result.score < 1.0


def test_grammar_evaluator_all_bad():
    result = GrammarEvaluator().evaluate(
        sentence="",
        translation="",
        constraints=CONSTRAINTS,
    )
    assert result.score == 0.0


def test_grammar_evaluator_case_insensitive_keyword():
    result = GrammarEvaluator().evaluate(
        sentence="COMIMOS mucho.",
        translation="We ate a lot.",
        constraints=CONSTRAINTS,
    )
    assert result.details["has_keyword_stem"] is True


def test_grammar_evaluator_short_keyword():
    """Keywords shorter than 3 chars use the full keyword as stem."""
    result = GrammarEvaluator().evaluate(
        sentence="Yo fui al parque.",
        translation="I went to the park.",
        constraints={**CONSTRAINTS, "keyword": "ir"},
    )
    assert result.details["has_keyword_stem"] is False

    result2 = GrammarEvaluator().evaluate(
        sentence="Yo quiero ir al parque.",
        translation="I want to go to the park.",
        constraints={**CONSTRAINTS, "keyword": "ir"},
    )
    assert result2.details["has_keyword_stem"] is True


def test_grammar_evaluator_no_keyword_in_constraints():
    """If keyword is missing from constraints, stem is empty -> always matches."""
    result = GrammarEvaluator().evaluate(
        sentence="Hola mundo.",
        translation="Hello world.",
        constraints={},
    )
    assert result.details["has_keyword_stem"] is True
