"""Integration test: run the full mock pipeline and verify DB state."""

from __future__ import annotations

from research.db.models import ConstraintSet, Experiment, GeneratedSentence
from research.run_experiment import (
    MOCK_OUTPUTS,
    PHASE1_CONSTRAINT_SETS,
    _ensure_constraint_sets,
)


def test_ensure_constraint_sets_inserts_on_first_call(session):
    assert session.query(ConstraintSet).count() == 0
    result = _ensure_constraint_sets(session)
    assert len(result) == len(PHASE1_CONSTRAINT_SETS)
    assert session.query(ConstraintSet).count() == len(PHASE1_CONSTRAINT_SETS)


def test_ensure_constraint_sets_is_idempotent(session):
    first = _ensure_constraint_sets(session)
    second = _ensure_constraint_sets(session)
    assert len(first) == len(second)
    assert session.query(ConstraintSet).count() == len(PHASE1_CONSTRAINT_SETS)


def test_full_mock_pipeline(session):
    """Run the full mock generation loop and verify everything lands in the DB."""
    constraint_sets = _ensure_constraint_sets(session)

    experiment = Experiment(
        name="test_mock_run",
        method="baseline_gpt",
        samples_per_case=3,
        config={"live": False, "model": "gpt-4o", "temperature": 0.7},
        status="running",
    )
    session.add(experiment)
    session.commit()

    total_stored = 0
    for cs in constraint_sets:
        candidates = MOCK_OUTPUTS.get(cs.keyword, [])[:3]
        for i, cand in enumerate(candidates):
            session.add(GeneratedSentence(
                experiment_id=experiment.id,
                constraint_set_id=cs.id,
                sentence=cand["sentence"],
                translation=cand["translation"],
                sample_index=i,
                generation_meta={"method": "baseline_gpt", "live": False},
            ))
            total_stored += 1
        session.commit()

    experiment.status = "completed"
    session.commit()

    assert experiment.status == "completed"
    assert session.query(GeneratedSentence).count() == total_stored
    assert total_stored == 15

    for cs in constraint_sets:
        count = (
            session.query(GeneratedSentence)
            .filter_by(experiment_id=experiment.id, constraint_set_id=cs.id)
            .count()
        )
        assert count == 3, f"Expected 3 sentences for {cs.keyword}, got {count}"


def test_mock_outputs_cover_all_constraint_sets():
    """Every hardcoded constraint set should have mock data."""
    for cs in PHASE1_CONSTRAINT_SETS:
        assert cs["keyword"] in MOCK_OUTPUTS, f"No mock data for {cs['keyword']}"
        assert len(MOCK_OUTPUTS[cs["keyword"]]) >= 3


def test_constraint_sets_have_target_language(session):
    constraint_sets = _ensure_constraint_sets(session)
    for cs in constraint_sets:
        assert cs.target_language == "es"
