"""Tests for distribution-level (group) metrics."""

from __future__ import annotations

from research.db.models import GeneratedSentence, SentenceEvaluation
from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.distribution.uniqueness import UniquenessRatioMetric
from research.run_experiment import _compute_and_store_group_metrics


def test_uniqueness_ratio_all_distinct():
    m = UniquenessRatioMetric("constraint_set")
    s1 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Uno.",
        translation="One.",
        sample_index=0,
    )
    s2 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="Dos.",
        translation="Two.",
        sample_index=1,
    )
    r = m.compute([s1, s2])
    assert r.value == 1.0
    assert r.details["unique"] == 2


def test_uniqueness_ratio_duplicates():
    m = UniquenessRatioMetric("constraint_set")
    s1 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="  Hola  ",
        translation="Hi.",
        sample_index=0,
    )
    s2 = GeneratedSentence(
        experiment_id=1,
        constraint_set_id=1,
        sentence="hola",
        translation="Hi.",
        sample_index=1,
    )
    r = m.compute([s1, s2])
    assert r.value == 0.5


def test_compute_and_store_group_metrics_no_sentence_evaluations(
    session, sample_constraint_set, sample_experiment
):
    session.add(GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="X.",
        translation="X.",
        sample_index=0,
    ))
    session.commit()
    assert session.query(SentenceEvaluation).count() == 0

    n = _compute_and_store_group_metrics(
        session, sample_experiment, DEFAULT_GROUP_METRICS
    )
    assert n == 2  # uniqueness_ratio + uniqueness_ratio_experiment
    assert session.query(SentenceEvaluation).count() == 0
