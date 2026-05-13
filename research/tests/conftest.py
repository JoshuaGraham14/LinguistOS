"""Shared fixtures for research pipeline tests.

Uses an in-memory SQLite database so tests are fast, isolated,
and never touch the real research.db file.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from research.db.database import Base
from research.db.models import ConstraintSet, Experiment, GeneratedSentence  # noqa: F401


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
def sample_constraint_set(session) -> ConstraintSet:
    cs = ConstraintSet(
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
def sample_experiment(session) -> Experiment:
    exp = Experiment(
        name="test_experiment",
        method="baseline_gpt",
        samples_per_case=3,
        config={"model": "gpt-4o", "temperature": 0.7},
        status="pending",
    )
    session.add(exp)
    session.commit()
    return exp
