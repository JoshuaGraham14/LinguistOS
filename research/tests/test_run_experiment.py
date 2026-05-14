"""Integration test: run the full mock pipeline and verify DB state."""

from __future__ import annotations

from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    SentenceEvaluation,
)
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.grammar import GrammarEvaluator
from research.run_experiment import (
    MOCK_OUTPUTS,
    _compute_and_store_group_metrics,
    _evaluate_sentences,
)


BENCHMARK_CONSTRAINT_SETS = [
    {"keyword": "comer", "translation": "to eat", "tense": "past", "person": "1st", "number": "plural"},
    {"keyword": "vivir", "translation": "to live", "tense": "future", "person": "3rd", "number": "singular"},
    {"keyword": "hablar", "translation": "to speak", "tense": "present", "person": "2nd", "number": "singular"},
    {"keyword": "escribir", "translation": "to write", "tense": "past", "person": "3rd", "number": "plural"},
    {"keyword": "correr", "translation": "to run", "tense": "present", "person": "1st", "number": "singular"},
]


def _create_test_benchmark(session) -> tuple[Benchmark, list[ConstraintSet]]:
    """Create a benchmark with the standard 5 constraint sets for tests."""
    bm = Benchmark(name="test_spanish", language="es")
    session.add(bm)
    session.flush()

    sets = []
    for cs_data in BENCHMARK_CONSTRAINT_SETS:
        cs = ConstraintSet(benchmark_id=bm.id, target_language="es", **cs_data)
        session.add(cs)
        sets.append(cs)
    session.commit()
    return bm, sets


def test_full_mock_pipeline(session):
    """Run the full mock generation loop and verify everything lands in the DB."""
    benchmark, constraint_sets = _create_test_benchmark(session)

    experiment = Experiment(
        benchmark_id=benchmark.id,
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


def test_mock_outputs_cover_all_benchmark_keywords():
    """Every benchmark constraint set keyword should have mock data."""
    for cs in BENCHMARK_CONSTRAINT_SETS:
        assert cs["keyword"] in MOCK_OUTPUTS, f"No mock data for {cs['keyword']}"
        assert len(MOCK_OUTPUTS[cs["keyword"]]) >= 3


def test_experiment_links_to_benchmark(session):
    benchmark, constraint_sets = _create_test_benchmark(session)

    exp = Experiment(
        benchmark_id=benchmark.id,
        name="test_link",
        method="baseline_gpt",
        samples_per_case=3,
        status="pending",
    )
    session.add(exp)
    session.commit()

    row = session.query(Experiment).filter_by(name="test_link").one()
    assert row.benchmark_id == benchmark.id
    assert row.benchmark.name == "test_spanish"


# ── Evaluation integration ──────────────────────────────────────────────────


def test_evaluate_sentences_stores_evaluations(session):
    """Run the full pipeline with evaluation and verify evaluation rows."""
    benchmark, constraint_sets = _create_test_benchmark(session)

    experiment = Experiment(
        benchmark_id=benchmark.id,
        name="test_eval_run",
        method="baseline_gpt",
        samples_per_case=3,
        config={"live": False},
        status="running",
    )
    session.add(experiment)
    session.commit()

    for cs in constraint_sets:
        candidates = MOCK_OUTPUTS.get(cs.keyword, [])[:3]
        for i, cand in enumerate(candidates):
            session.add(GeneratedSentence(
                experiment_id=experiment.id,
                constraint_set_id=cs.id,
                sentence=cand["sentence"],
                translation=cand["translation"],
                sample_index=i,
            ))
    session.commit()

    evaluators = [GrammarEvaluator()]
    total = _evaluate_sentences(session, experiment, evaluators)

    assert total == 15  # 5 constraint sets × 3 sentences × 1 evaluator
    assert session.query(SentenceEvaluation).count() == 15

    for ev in session.query(SentenceEvaluation).all():
        assert ev.evaluator_name == "grammar_stub"
        assert 0.0 <= ev.score <= 1.0
        assert ev.details is not None


def test_evaluate_with_multiple_evaluators(session, sample_constraint_set, sample_experiment):
    """Multiple evaluators each produce one evaluation per sentence."""
    sent = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        sample_index=0,
    )
    session.add(sent)
    session.commit()

    class DummyEval(BaseEvaluator):
        @property
        def name(self):
            return "dummy"

        def evaluate(self, sentence, translation, constraints):
            return EvaluationResult(score=0.42)

    total = _evaluate_sentences(
        session, sample_experiment, [GrammarEvaluator(), DummyEval()]
    )
    assert total == 2
    names = {e.evaluator_name for e in session.query(SentenceEvaluation).all()}
    assert names == {"grammar_stub", "dummy"}


def test_evaluate_no_sentences_produces_zero_evaluations(session, sample_experiment):
    """If the experiment has no sentences, evaluation produces nothing."""
    total = _evaluate_sentences(session, sample_experiment, [GrammarEvaluator()])
    assert total == 0
    assert session.query(SentenceEvaluation).count() == 0


def test_full_phase3_metrics_pipeline(session):
    """After generation + sentence eval: group metrics + roll-ups land in experiment_metrics."""
    benchmark, constraint_sets = _create_test_benchmark(session)
    experiment = Experiment(
        benchmark_id=benchmark.id,
        name="phase3_integration",
        method="baseline_gpt",
        samples_per_case=3,
        config={"live": False},
        status="running",
    )
    session.add(experiment)
    session.commit()

    for cs in constraint_sets:
        for i, cand in enumerate(MOCK_OUTPUTS.get(cs.keyword, [])[:3]):
            session.add(GeneratedSentence(
                experiment_id=experiment.id,
                constraint_set_id=cs.id,
                sentence=cand["sentence"],
                translation=cand["translation"],
                sample_index=i,
            ))
    session.commit()

    _evaluate_sentences(session, experiment, [GrammarEvaluator()])
    assert session.query(SentenceEvaluation).count() == 15

    g = _compute_and_store_group_metrics(session, experiment, DEFAULT_GROUP_METRICS)
    assert g == 6  # 5 constraint_set + 1 experiment uniqueness metrics

    r = aggregate_sentence_eval_rollups(session, experiment.id)
    assert r == 6  # mean::grammar_stub per CS + experiment-wide

    assert session.query(ExperimentMetric).count() == 12
