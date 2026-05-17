"""Tests for roll-up aggregation (Stage 2a)."""

from __future__ import annotations

import pytest

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
    assert n == 8  # 4 kinds × (1 constraint_set + 1 experiment) per evaluator

    cs_mean = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="mean::e1")
        .one()
    )
    assert cs_mean.value == 0.5
    assert cs_mean.constraint_set_id == sample_constraint_set.id

    cs_min = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="min::e1")
        .one()
    )
    assert cs_min.value == 0.0

    cs_std = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="std::e1")
        .one()
    )
    assert cs_std.value == pytest.approx(0.5)

    cs_pass = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="pass_rate::e1")
        .one()
    )
    assert cs_pass.value == 0.5
    assert cs_pass.breakdown["pass_threshold"] == 0.5

    ex_mean = (
        session.query(ExperimentMetric)
        .filter_by(scope="experiment", metric_name="mean::e1")
        .one()
    )
    assert ex_mean.constraint_set_id is None
    assert ex_mean.value == 0.5


def test_aggregate_rollups_std_single_score_is_zero(session, sample_constraint_set, sample_experiment):
    sent = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="A.",
        translation="A.",
        sample_index=0,
    )
    session.add(sent)
    session.commit()
    session.add(SentenceEvaluation(sentence_id=sent.id, evaluator_name="e1", score=0.8))
    session.commit()

    aggregate_sentence_eval_rollups(session, sample_experiment.id)

    std_row = (
        session.query(ExperimentMetric)
        .filter_by(scope="constraint_set", metric_name="std::e1")
        .one()
    )
    assert std_row.value == 0.0


def test_aggregate_rollups_empty_when_no_evaluations(session, sample_experiment):
    assert aggregate_sentence_eval_rollups(session, sample_experiment.id) == 0
    assert session.query(ExperimentMetric).count() == 0


def test_aggregate_rollups_idempotent_replaces_old_rows(
    session, sample_constraint_set, sample_experiment
):
    sent = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="A.",
        translation="A.",
        sample_index=0,
    )
    session.add(sent)
    session.commit()
    session.add(SentenceEvaluation(sentence_id=sent.id, evaluator_name="e1", score=1.0))
    session.commit()

    aggregate_sentence_eval_rollups(session, sample_experiment.id)
    first_count = session.query(ExperimentMetric).count()

    aggregate_sentence_eval_rollups(session, sample_experiment.id)
    second_count = session.query(ExperimentMetric).count()
    assert first_count == second_count == 8
