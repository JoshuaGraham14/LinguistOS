"""Tests for research database models: schema, relationships, cascades."""

from __future__ import annotations

import pytest

from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    MethodConfig,
    SentenceEvaluation,
)


# ── Benchmark ──────────────────────────────────────────────────────────────


def test_benchmark_creation(session):
    bm = Benchmark(name="spanish_basic", language="es", description="Basic Spanish")
    session.add(bm)
    session.commit()

    row = session.query(Benchmark).filter_by(name="spanish_basic").one()
    assert row.language == "es"
    assert row.description == "Basic Spanish"
    assert row.created_at is not None


def test_benchmark_name_unique(session):
    session.add(Benchmark(name="dup", language="es"))
    session.commit()
    with pytest.raises(Exception):
        session.add(Benchmark(name="dup", language="es"))
        session.commit()


def test_cascade_delete_benchmark_removes_constraint_sets(session):
    bm = Benchmark(name="to_delete", language="es")
    session.add(bm)
    session.flush()
    session.add(ConstraintSet(
        benchmark_id=bm.id, keyword="x", translation="y",
        tense="present", person="1st", number="singular", target_language="es",
    ))
    session.commit()
    assert session.query(ConstraintSet).count() == 1

    session.delete(bm)
    session.commit()
    assert session.query(ConstraintSet).count() == 0


# ── ConstraintSet ──────────────────────────────────────────────────────────


def test_constraint_set_creation(session, sample_benchmark):
    cs = ConstraintSet(
        benchmark_id=sample_benchmark.id,
        keyword="vivir",
        translation="to live",
        tense="future",
        person="3rd",
        number="singular",
        target_language="es",
    )
    session.add(cs)
    session.commit()

    row = session.query(ConstraintSet).filter_by(keyword="vivir").one()
    assert row.tense == "future"
    assert row.person == "3rd"
    assert row.target_language == "es"
    assert row.cefr_level is None
    assert row.created_at is not None
    assert row.benchmark_id == sample_benchmark.id


def test_constraint_set_with_cefr(session, sample_benchmark):
    cs = ConstraintSet(
        benchmark_id=sample_benchmark.id,
        keyword="hablar",
        translation="to speak",
        tense="present",
        person="2nd",
        number="singular",
        target_language="es",
        cefr_level="B1",
    )
    session.add(cs)
    session.commit()

    row = session.query(ConstraintSet).filter_by(keyword="hablar").one()
    assert row.cefr_level == "B1"


def test_constraint_set_extra_constraints_json(session, sample_benchmark):
    cs = ConstraintSet(
        benchmark_id=sample_benchmark.id,
        keyword="ser",
        translation="to be",
        tense="present",
        person="1st",
        number="singular",
        target_language="es",
        extra_constraints={"mood": "subjunctive", "formality": "formal"},
    )
    session.add(cs)
    session.commit()

    row = session.query(ConstraintSet).filter_by(keyword="ser").one()
    assert row.extra_constraints["mood"] == "subjunctive"
    assert row.extra_constraints["formality"] == "formal"


def test_constraint_set_to_constraints_dict(session, sample_benchmark):
    cs = ConstraintSet(
        benchmark_id=sample_benchmark.id,
        keyword="comer",
        expected_form="comimos",
        translation="to eat",
        tense="preterite",
        person="1st",
        number="plural",
        target_language="es",
        cefr_level="A2",
        extra_constraints={"mood": "indicative"},
    )
    d = cs.to_constraints_dict()
    assert d["keyword"] == "comer"
    assert d["expected_form"] == "comimos"
    assert d["translation"] == "to eat"
    assert d["tense"] == "preterite"
    assert d["person"] == "1st"
    assert d["number"] == "plural"
    assert d["target_language"] == "es"
    assert d["cefr_level"] == "A2"
    assert d["extra_constraints"] == {"mood": "indicative"}


def test_constraint_set_to_constraints_dict_omits_expected_form_when_none(
    session, sample_constraint_set
):
    sample_constraint_set.expected_form = None
    d = sample_constraint_set.to_constraints_dict()
    assert "expected_form" not in d


def test_constraint_set_to_constraints_dict_omits_extra_when_none(
    session, sample_constraint_set
):
    d = sample_constraint_set.to_constraints_dict()
    assert "extra_constraints" not in d
    assert d["keyword"] == "comer"


# ── MethodConfig ───────────────────────────────────────────────────────────


def test_method_config_creation(session):
    mc = MethodConfig(
        name="test_cfg",
        method="baseline_gpt",
        samples_per_case=5,
        config={"model": "gpt-4o", "temperature": 0.7},
    )
    session.add(mc)
    session.commit()

    row = session.query(MethodConfig).filter_by(name="test_cfg").one()
    assert row.method == "baseline_gpt"
    assert row.samples_per_case == 5
    assert row.config["model"] == "gpt-4o"
    assert row.created_at is not None


def test_method_config_name_unique(session):
    session.add(MethodConfig(name="dup", method="x", samples_per_case=1))
    session.commit()
    with pytest.raises(Exception):
        session.add(MethodConfig(name="dup", method="x", samples_per_case=1))
        session.commit()


# ── Experiment ─────────────────────────────────────────────────────────────


def test_experiment_creation(session):
    exp = Experiment(
        name="test_run",
        status="pending",
    )
    session.add(exp)
    session.commit()

    row = session.query(Experiment).filter_by(name="test_run").one()
    assert row.status == "pending"
    assert row.completed_at is None
    assert row.benchmark_id is None
    assert row.method_config_id is None


def test_experiment_links_to_method_config(session, sample_method_config):
    exp = Experiment(
        name="linked",
        method_config_id=sample_method_config.id,
        status="pending",
    )
    session.add(exp)
    session.commit()

    row = session.query(Experiment).filter_by(name="linked").one()
    assert row.method_config_id == sample_method_config.id
    assert row.method_config.method == "baseline_gpt"


def test_generated_sentence_belongs_to_experiment_and_constraint_set(
    session, sample_constraint_set, sample_experiment
):
    gen = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        sample_index=0,
    )
    session.add(gen)
    session.commit()

    row = session.query(GeneratedSentence).one()
    assert row.experiment.name == "test_experiment"
    assert row.constraint_set.keyword == "comer"
    assert row.sentence == "Nosotros comimos pizza."
    assert row.sample_index == 0


def test_generated_sentence_meta_json(session, sample_constraint_set, sample_experiment):
    gen = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="Comimos en casa.",
        translation="We ate at home.",
        sample_index=0,
        generation_meta={"method": "baseline_gpt", "live": False},
    )
    session.add(gen)
    session.commit()

    row = session.query(GeneratedSentence).one()
    assert row.generation_meta["method"] == "baseline_gpt"
    assert row.generation_meta["live"] is False


def test_cascade_delete_experiment_removes_sentences(
    session, sample_constraint_set, sample_experiment
):
    for i in range(3):
        session.add(GeneratedSentence(
            experiment_id=sample_experiment.id,
            constraint_set_id=sample_constraint_set.id,
            sentence=f"Sentence {i}",
            translation=f"Translation {i}",
            sample_index=i,
        ))
    session.commit()
    assert session.query(GeneratedSentence).count() == 3

    session.delete(sample_experiment)
    session.commit()
    assert session.query(GeneratedSentence).count() == 0


def test_cascade_delete_constraint_set_removes_sentences(
    session, sample_constraint_set, sample_experiment
):
    for i in range(3):
        session.add(GeneratedSentence(
            experiment_id=sample_experiment.id,
            constraint_set_id=sample_constraint_set.id,
            sentence=f"Sentence {i}",
            translation=f"Translation {i}",
            sample_index=i,
        ))
    session.commit()
    assert session.query(GeneratedSentence).count() == 3

    session.delete(sample_constraint_set)
    session.commit()
    assert session.query(GeneratedSentence).count() == 0


def test_experiment_sentences_relationship(
    session, sample_constraint_set, sample_experiment
):
    for i in range(2):
        session.add(GeneratedSentence(
            experiment_id=sample_experiment.id,
            constraint_set_id=sample_constraint_set.id,
            sentence=f"Sentence {i}",
            translation=f"Translation {i}",
            sample_index=i,
        ))
    session.commit()

    session.refresh(sample_experiment)
    assert len(sample_experiment.sentences) == 2
    assert sample_experiment.sentences[0].sentence == "Sentence 0"


# ── SentenceEvaluation ──────────────────────────────────────────────────────


def test_sentence_evaluation_creation(session, sample_sentence):
    ev = SentenceEvaluation(
        sentence_id=sample_sentence.id,
        evaluator_name="grammar_stub",
        score=0.85,
        details={"has_keyword_stem": True, "has_translation": True},
    )
    session.add(ev)
    session.commit()

    row = session.query(SentenceEvaluation).one()
    assert row.evaluator_name == "grammar_stub"
    assert row.score == 0.85
    assert row.details["has_keyword_stem"] is True
    assert row.created_at is not None


def test_sentence_evaluation_belongs_to_sentence(session, sample_sentence):
    ev = SentenceEvaluation(
        sentence_id=sample_sentence.id,
        evaluator_name="test_eval",
        score=1.0,
    )
    session.add(ev)
    session.commit()

    row = session.query(SentenceEvaluation).one()
    assert row.sentence.sentence == "Nosotros comimos pizza anoche."


def test_sentence_evaluations_relationship(session, sample_sentence):
    for i in range(3):
        session.add(SentenceEvaluation(
            sentence_id=sample_sentence.id,
            evaluator_name=f"evaluator_{i}",
            score=0.5 + i * 0.1,
        ))
    session.commit()

    session.refresh(sample_sentence)
    assert len(sample_sentence.evaluations) == 3


def test_cascade_delete_sentence_removes_evaluations(session, sample_sentence):
    for i in range(2):
        session.add(SentenceEvaluation(
            sentence_id=sample_sentence.id,
            evaluator_name=f"evaluator_{i}",
            score=0.9,
        ))
    session.commit()
    assert session.query(SentenceEvaluation).count() == 2

    session.delete(sample_sentence)
    session.commit()
    assert session.query(SentenceEvaluation).count() == 0


def test_evaluation_details_nullable(session, sample_sentence):
    ev = SentenceEvaluation(
        sentence_id=sample_sentence.id,
        evaluator_name="minimal",
        score=0.5,
    )
    session.add(ev)
    session.commit()

    row = session.query(SentenceEvaluation).one()
    assert row.details is None


# ── ExperimentMetric ────────────────────────────────────────────────────────


def test_experiment_metric_creation(session, sample_experiment, sample_constraint_set):
    m = ExperimentMetric(
        experiment_id=sample_experiment.id,
        metric_name="uniqueness_ratio",
        value=0.75,
        scope="constraint_set",
        constraint_set_id=sample_constraint_set.id,
        breakdown={"unique": 3, "n": 4},
    )
    session.add(m)
    session.commit()

    row = session.query(ExperimentMetric).one()
    assert row.metric_name == "uniqueness_ratio"
    assert row.value == 0.75
    assert row.scope == "constraint_set"
    assert row.constraint_set_id == sample_constraint_set.id
    assert row.breakdown["n"] == 4


def test_experiment_metric_experiment_scope_null_constraint_set(session, sample_experiment):
    m = ExperimentMetric(
        experiment_id=sample_experiment.id,
        metric_name="mean::grammar_stub",
        value=0.9,
        scope="experiment",
        constraint_set_id=None,
    )
    session.add(m)
    session.commit()

    row = session.query(ExperimentMetric).one()
    assert row.scope == "experiment"
    assert row.constraint_set_id is None


def test_cascade_delete_experiment_removes_metrics(session, sample_experiment, sample_constraint_set):
    session.add(ExperimentMetric(
        experiment_id=sample_experiment.id,
        metric_name="x",
        value=1.0,
        scope="experiment",
        constraint_set_id=None,
    ))
    session.add(ExperimentMetric(
        experiment_id=sample_experiment.id,
        metric_name="y",
        value=0.5,
        scope="constraint_set",
        constraint_set_id=sample_constraint_set.id,
    ))
    session.commit()
    assert session.query(ExperimentMetric).count() == 2

    session.delete(sample_experiment)
    session.commit()
    assert session.query(ExperimentMetric).count() == 0
