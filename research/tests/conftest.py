"""Shared fixtures for research pipeline tests.

Uses an in-memory SQLite database so tests are fast, isolated,
and never touch the real research.db file.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from research.db.database import Base
from research.db.models import (  # noqa: F401
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    SentenceEvaluation,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(eng, "connect")
    def _enable_fks(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def sample_benchmark(session) -> Benchmark:
    bm = Benchmark(name="test_benchmark", language="es", description="Test benchmark")
    session.add(bm)
    session.commit()
    return bm


@pytest.fixture
def sample_constraint_set(session, sample_benchmark) -> ConstraintSet:
    cs = ConstraintSet(
        benchmark_id=sample_benchmark.id,
        keyword="comer",
        translation="to eat",
        tense="past",
        person="1st",
        number="plural",
        target_language="es",
    )
    session.add(cs)
    session.commit()
    return cs


@pytest.fixture
def sample_experiment(session, sample_benchmark) -> Experiment:
    exp = Experiment(
        benchmark_id=sample_benchmark.id,
        name="test_experiment",
        method="baseline_gpt",
        samples_per_case=3,
        config={"model": "gpt-4o", "temperature": 0.7},
        status="pending",
    )
    session.add(exp)
    session.commit()
    return exp


@pytest.fixture
def sample_sentence(session, sample_constraint_set, sample_experiment) -> GeneratedSentence:
    sent = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="Nosotros comimos pizza anoche.",
        translation="We ate pizza last night.",
        sample_index=0,
    )
    session.add(sent)
    session.commit()
    return sent
