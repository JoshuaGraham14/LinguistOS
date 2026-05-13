"""Tests for research database models: schema, relationships, cascades."""

from __future__ import annotations

from research.db.models import ConstraintSet, Experiment, GeneratedSentence


def test_constraint_set_creation(session):
    cs = ConstraintSet(
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


def test_constraint_set_with_cefr(session):
    cs = ConstraintSet(
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


def test_constraint_set_extra_constraints_json(session):
    cs = ConstraintSet(
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


def test_experiment_creation(session):
    exp = Experiment(
        name="test_run",
        method="baseline_gpt",
        samples_per_case=5,
        config={"model": "gpt-4o", "temperature": 0.7},
        status="pending",
    )
    session.add(exp)
    session.commit()

    row = session.query(Experiment).filter_by(name="test_run").one()
    assert row.method == "baseline_gpt"
    assert row.samples_per_case == 5
    assert row.config["model"] == "gpt-4o"
    assert row.status == "pending"
    assert row.completed_at is None


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
