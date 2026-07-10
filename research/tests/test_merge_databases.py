"""Tests for merging per-job SQLite databases."""

from __future__ import annotations

from pathlib import Path

from research.db.database import create_engine_for_path, init_db
from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    MethodConfig,
    SentenceEvaluation,
)
from research.merge_databases import merge_database
from sqlalchemy.orm import sessionmaker


def _write_run_db(path: Path) -> None:
    init_db(path)
    Session = sessionmaker(bind=create_engine_for_path(path), autoflush=False, autocommit=False)
    session = Session()
    try:
        bm = Benchmark(name="merge_bench", language="es")
        session.add(bm)
        session.flush()
        cs = ConstraintSet(
            benchmark_id=bm.id,
            keyword="comer",
            translation="to eat",
            constraints={"tense": "present", "person": "1st", "number": "singular"},
            target_language="es",
        )
        session.add(cs)
        mc = MethodConfig(name="merge_method", method="baseline_gpt", samples_per_case=1)
        session.add(mc)
        session.flush()
        exp = Experiment(
            benchmark_id=bm.id,
            method_config_id=mc.id,
            name="merge_bench__merge_method__live",
            status="completed",
        )
        session.add(exp)
        session.flush()
        sent = GeneratedSentence(
            experiment_id=exp.id,
            constraint_set_id=cs.id,
            sentence="Como pizza.",
            translation="I eat pizza.",
            sample_index=0,
        )
        session.add(sent)
        session.flush()
        session.add(
            SentenceEvaluation(
                sentence_id=sent.id,
                evaluator_name="length",
                score=1.0,
            )
        )
        session.add(
            ExperimentMetric(
                experiment_id=exp.id,
                metric_name="pass_rate::length",
                value=1.0,
                scope="experiment",
            )
        )
        session.commit()
    finally:
        session.close()


def _target_session(path: Path):
    init_db(path)
    Session = sessionmaker(bind=create_engine_for_path(path), autoflush=False, autocommit=False)
    session = Session()
    bm = Benchmark(name="merge_bench", language="es")
    session.add(bm)
    session.flush()
    session.add(
        ConstraintSet(
            benchmark_id=bm.id,
            keyword="comer",
            translation="to eat",
            constraints={"tense": "present", "person": "1st", "number": "singular"},
            target_language="es",
        )
    )
    session.add(MethodConfig(name="merge_method", method="baseline_gpt", samples_per_case=1))
    session.commit()
    session.close()
    return Session


def test_merge_database_copies_experiment(tmp_path):
    source = tmp_path / "run.db"
    target = tmp_path / "main.db"
    _write_run_db(source)
    _target_session(target)

    stats = merge_database(source, target)

    assert stats.experiments_merged == 1
    assert stats.sentences_added == 1
    assert stats.evaluations_added == 1
    assert stats.metrics_added == 1

    Session = sessionmaker(bind=create_engine_for_path(target), autoflush=False, autocommit=False)
    session = Session()
    try:
        exp = session.query(Experiment).filter_by(name="merge_bench__merge_method__live").one()
        assert exp.status == "completed"
        assert session.query(GeneratedSentence).filter_by(experiment_id=exp.id).count() == 1
    finally:
        session.close()


def test_merge_database_is_idempotent(tmp_path):
    source = tmp_path / "run.db"
    target = tmp_path / "main.db"
    _write_run_db(source)
    _target_session(target)

    first = merge_database(source, target)
    second = merge_database(source, target)

    assert first.sentences_added == 1
    assert second.sentences_added == 0
    assert second.evaluations_added == 0
    assert second.metrics_added == 0
