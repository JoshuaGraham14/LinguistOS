"""Tests for grammar-only rescore helpers."""

from __future__ import annotations

from typing import Any

from research.db.models import Experiment, GeneratedSentence, SentenceEvaluation
from research.evaluation.rescore import (
    clear_sentence_evaluations_for_evaluator,
    rescore_evaluator_for_experiment,
    rescore_grammar_languagetool,
)
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult


class _ToggleGrammarEval(BaseEvaluator):
    def __init__(self) -> None:
        self._pass = False

    @property
    def name(self) -> str:
        return "grammar_languagetool"

    def evaluate(self, sentence: str, translation: str, constraints: dict[str, Any]):
        self._pass = not self._pass
        score = 1.0 if self._pass else 0.0
        return EvaluationResult(score=score, details={"passed": bool(score)})


def _add_sentence(session, experiment, constraint_set) -> GeneratedSentence:
    sent = GeneratedSentence(
        experiment_id=experiment.id,
        constraint_set_id=constraint_set.id,
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        sample_index=0,
        generation_meta={"sentence_length": "short"},
    )
    session.add(sent)
    session.commit()
    return sent


def test_clear_sentence_evaluations_scoped_to_evaluator(
    session, sample_experiment, sample_constraint_set
):
    sent = _add_sentence(session, sample_experiment, sample_constraint_set)
    session.add_all(
        [
            SentenceEvaluation(
                sentence_id=sent.id,
                evaluator_name="expected_form_match",
                score=1.0,
            ),
            SentenceEvaluation(
                sentence_id=sent.id,
                evaluator_name="grammar_languagetool",
                score=0.0,
            ),
        ]
    )
    session.commit()

    removed = clear_sentence_evaluations_for_evaluator(
        session, sample_experiment.id, "grammar_languagetool"
    )
    session.commit()
    assert removed == 1
    names = {
        row.evaluator_name
        for row in session.query(SentenceEvaluation).filter_by(sentence_id=sent.id).all()
    }
    assert names == {"expected_form_match"}


def test_rescore_evaluator_replaces_only_target_rows(
    session, sample_experiment, sample_constraint_set
):
    sent = _add_sentence(session, sample_experiment, sample_constraint_set)
    session.add(
        SentenceEvaluation(
            sentence_id=sent.id,
            evaluator_name="expected_form_match",
            score=1.0,
        )
    )
    session.add(
        SentenceEvaluation(
            sentence_id=sent.id,
            evaluator_name="grammar_languagetool",
            score=0.0,
            details={"error": "disk quota"},
        )
    )
    session.commit()

    grammar = _ToggleGrammarEval()
    count = rescore_evaluator_for_experiment(
        session, sample_experiment, grammar, commit_every=1
    )
    assert count == 1
    rows = {
        row.evaluator_name: row
        for row in session.query(SentenceEvaluation).filter_by(sentence_id=sent.id).all()
    }
    assert rows["expected_form_match"].score == 1.0
    assert rows["grammar_languagetool"].score == 1.0
    assert rows["grammar_languagetool"].details == {"passed": True}


def test_rescore_grammar_refreshes_rollups(
    session, sample_benchmark, sample_method_config, sample_constraint_set
):
    experiment = Experiment(
        benchmark_id=sample_benchmark.id,
        method_config_id=sample_method_config.id,
        name="grammar_rescore_test",
        status="completed",
    )
    session.add(experiment)
    session.flush()
    sent = _add_sentence(session, experiment, sample_constraint_set)
    session.add(
        SentenceEvaluation(
            sentence_id=sent.id,
            evaluator_name="expected_form_match",
            score=1.0,
        )
    )
    session.add(
        SentenceEvaluation(
            sentence_id=sent.id,
            evaluator_name="grammar_languagetool",
            score=0.0,
            details={"error": "disk quota", "match_count": 0, "token_count": 3},
        )
    )
    session.commit()
    aggregate_sentence_eval_rollups(session, experiment.id)

    grammar = _ToggleGrammarEval()
    stats = rescore_grammar_languagetool(
        session,
        experiment,
        evaluator=grammar,
        refresh_lt_breakdown=False,
    )
    assert stats["grammar_evals"] == 1
    assert stats["rollup_rows"] > 0

    pass_rate = (
        session.query(SentenceEvaluation)
        .filter_by(sentence_id=sent.id, evaluator_name="grammar_languagetool")
        .one()
        .score
    )
    assert pass_rate == 1.0
