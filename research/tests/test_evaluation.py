"""Tests for evaluation framework: BaseEvaluator ABC, sentence evaluators."""

from __future__ import annotations

import pytest

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.expected_form import (
    ExpectedFormMatchEvaluator,
    normalize_token,
    tokenize,
)
from research.evaluation.sentence.grammar import GrammarEvaluator
from research.fixtures.mock_outputs import MOCK_OUTPUTS


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
    "expected_form": "comimos",
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


# ── ExpectedFormMatchEvaluator ───────────────────────────────────────────────


def test_expected_form_match_evaluator_name():
    assert ExpectedFormMatchEvaluator().name == "expected_form_match"


def test_expected_form_match_passes_on_gold_form():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 1.0
    assert result.details["passed"] is True
    assert result.details["matched_token"] == "comimos"


def test_expected_form_match_fails_on_wrong_form():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Nosotros comemos pizza.",
        translation="We eat pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 0.0
    assert result.details["passed"] is False
    assert result.details["matched_token"] is None


def test_expected_form_match_fails_on_infinitive_when_expecting_conjugated():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Me gusta comer pizza.",
        translation="I like to eat pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 0.0


def test_expected_form_match_case_insensitive():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Nosotros COMIMOS pizza.",
        translation="We ate pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 1.0
    assert result.details["matched_token"] == "COMIMOS"


def test_expected_form_match_punctuation_on_token_edges():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="¡Comimos!",
        translation="We ate!",
        constraints=CONSTRAINTS,
    )
    assert result.score == 1.0
    assert result.details["matched_token"] == "Comimos"


def test_expected_form_match_no_substring_inside_longer_word():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Voy a recomendar el restaurante.",
        translation="I am going to recommend the restaurant.",
        constraints={**CONSTRAINTS, "expected_form": "comer"},
    )
    assert result.score == 0.0


def test_expected_form_match_accent_sensitive():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Ayer comio pasta.",
        translation="Yesterday he ate pasta.",
        constraints={**CONSTRAINTS, "expected_form": "comió"},
    )
    assert result.score == 0.0

    result2 = ExpectedFormMatchEvaluator().evaluate(
        sentence="Ayer comió pasta.",
        translation="Yesterday he ate pasta.",
        constraints={**CONSTRAINTS, "expected_form": "comió"},
    )
    assert result2.score == 1.0


def test_expected_form_match_missing_expected_form():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        constraints={k: v for k, v in CONSTRAINTS.items() if k != "expected_form"},
    )
    assert result.score == 0.0
    assert result.details["reason"] == "missing_expected_form"


def test_expected_form_match_empty_sentence():
    result = ExpectedFormMatchEvaluator().evaluate(
        sentence="",
        translation="We ate pizza.",
        constraints=CONSTRAINTS,
    )
    assert result.score == 0.0
    assert result.details["tokens_checked"] == 0


def test_tokenize_strips_punctuation():
    assert tokenize("¡Hola, mundo!") == ["Hola", "mundo"]


def test_normalize_token_casefolds():
    assert normalize_token("COMIMOS") == normalize_token("comimos")


@pytest.mark.parametrize(
    ("keyword", "expected_form"),
    [
        ("comer", "comimos"),
        ("vivir", "vivirá"),
        ("hablar", "hablas"),
        ("escribir", "escribieron"),
        ("correr", "corro"),
    ],
)
def test_mock_outputs_pass_expected_form_match(keyword, expected_form):
    evaluator = ExpectedFormMatchEvaluator()
    constraints = {**CONSTRAINTS, "keyword": keyword, "expected_form": expected_form}
    for cand in MOCK_OUTPUTS[keyword]:
        result = evaluator.evaluate(
            sentence=cand["sentence"],
            translation=cand["translation"],
            constraints=constraints,
        )
        assert result.score == 1.0, cand["sentence"]
