"""Tests for roll-up aggregation (Stage 2a)."""

from __future__ import annotations

from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.db.models import ExperimentMetric, GeneratedSentence, SentenceEvaluation


def test_aggregate_rollups_mean_per_constraint_and_overall(
    session, sample_constraint_set, sample_experiment
):
    s1 = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="A.",
        translation="A.",
        sample_index=0,
    )
    s2 = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="B.",
        translation="B.",
        sample_index=1,
    )
    session.add_all([s1, s2])
    session.commit()

    session.add_all([
        SentenceEvaluation(sentence_id=s1.id, evaluator_name="e1", score=1.0),
        SentenceEvaluation(sentence_id=s2.id, evaluator_name="e1", score=0.0),
    ])
    session.commit()

    n = aggregate_sentence_eval_rollups(session, sample_experiment.id)
    assert n == 2  # one constraint_set + one experiment row per evaluator

    cs_rows = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="mean::e1")
        .all()
    )
    assert len(cs_rows) == 1
    assert cs_rows[0].value == 0.5
    assert cs_rows[0].constraint_set_id == sample_constraint_set.id

    ex_rows = (
        session.query(ExperimentMetric)
        .filter_by(scope="experiment", metric_name="mean::e1")
        .all()
    )
    assert len(ex_rows) == 1
    assert ex_rows[0].constraint_set_id is None
    assert ex_rows[0].value == 0.5


def test_aggregate_rollups_empty_when_no_evaluations(session, sample_experiment):
    assert aggregate_sentence_eval_rollups(session, sample_experiment.id) == 0
    assert session.query(ExperimentMetric).count() == 0
