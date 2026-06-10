"""Integration test: run the full mock pipeline and verify DB state."""

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
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence import DEFAULT_EVALUATORS
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.fixtures.mock_outputs import MOCK_OUTPUTS, get_mock_candidates
from research.generation.languages import extract_constraints
from research.pipeline import (
    _assert_live_allowed,
    _compute_and_store_group_metrics,
    _evaluate_sentences,
    _experiment_name,
)


BENCHMARK_CONSTRAINT_SETS = [
    {"keyword": "comer", "expected_form": "comimos", "translation": "to eat", "tense": "preterite", "person": "1st", "number": "plural"},
    {"keyword": "vivir", "expected_form": "vivirá", "translation": "to live", "tense": "future", "person": "3rd", "number": "singular"},
    {"keyword": "hablar", "expected_form": "hablas", "translation": "to speak", "tense": "present", "person": "2nd", "number": "singular"},
    {"keyword": "escribir", "expected_form": "escribieron", "translation": "to write", "tense": "preterite", "person": "3rd", "number": "plural"},
    {"keyword": "correr", "expected_form": "corro", "translation": "to run", "tense": "present", "person": "1st", "number": "singular"},
]


def _create_test_benchmark(session) -> tuple[Benchmark, list[ConstraintSet]]:
    """Create a benchmark with the standard 5 constraint sets for tests."""
    bm = Benchmark(name="test_spanish", language="es")
    session.add(bm)
    session.flush()

    sets = []
    for cs_data in BENCHMARK_CONSTRAINT_SETS:
        cs = ConstraintSet.from_yaml_dict(
            benchmark_id=bm.id,
            cs_data=cs_data,
            default_language="es",
            constraints=extract_constraints(cs_data),
        )
        session.add(cs)
        sets.append(cs)
    session.commit()
    return bm, sets


def _create_test_method_config(session) -> MethodConfig:
    mc = MethodConfig(
        name="test_baseline", method="baseline_gpt", samples_per_case=3,
        config={"model": "gpt-4o", "temperature": 0.7},
    )
    session.add(mc)
    session.commit()
    return mc


def test_full_mock_pipeline(session):
    """Run the full mock generation loop and verify everything lands in the DB."""
    benchmark, constraint_sets = _create_test_benchmark(session)
    method_config = _create_test_method_config(session)

    experiment = Experiment(
        benchmark_id=benchmark.id,
        method_config_id=method_config.id,
        name="test_mock_run",
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


def test_assert_live_allowed_rejects_mock_only_benchmark():
    bm = Benchmark(name="spanish_grammar_probe", language="es", mock_only=True)
    with pytest.raises(ValueError, match="mock_only"):
        _assert_live_allowed(bm, live=True)
    _assert_live_allowed(bm, live=False)


def test_mock_outputs_cover_spanish_basic_keywords():
    """Every spanish_basic constraint set keyword should have mock data."""
    for cs in BENCHMARK_CONSTRAINT_SETS:
        assert cs["keyword"] in MOCK_OUTPUTS, f"No mock data for {cs['keyword']}"
        assert len(MOCK_OUTPUTS[cs["keyword"]]) >= 3


def test_mock_outputs_cover_grammar_probe_keywords():
    probe_keywords = (
        "probe_subj_verb",
        "probe_det_noun",
        "probe_prep",
        "probe_correct",
    )
    for keyword in probe_keywords:
        cands = get_mock_candidates("spanish_grammar_probe", keyword)
        assert len(cands) >= 3, f"No mock data for {keyword}"


def test_default_evaluators_registry():
    names = {e.name for e in DEFAULT_EVALUATORS}
    assert names == {
        "expected_form_match",
        "verb_morphology",
        "grammar_languagetool",
        "length_in_band",
        "clause_count",
    }


def test_experiment_links_to_benchmark_and_method(session):
    benchmark, _ = _create_test_benchmark(session)
    method_config = _create_test_method_config(session)

    exp = Experiment(
        benchmark_id=benchmark.id,
        method_config_id=method_config.id,
        name="test_link",
        status="pending",
    )
    session.add(exp)
    session.commit()

    row = session.query(Experiment).filter_by(name="test_link").one()
    assert row.benchmark_id == benchmark.id
    assert row.benchmark.name == "test_spanish"
    assert row.method_config_id == method_config.id
    assert row.method_config.method == "baseline_gpt"


def test_experiment_name_uses_method_preset_name(session):
    benchmark, _ = _create_test_benchmark(session)
    method_config = _create_test_method_config(session)
    method_config.name = "baseline_long_explicit"
    session.commit()

    name = _experiment_name(
        benchmark=benchmark,
        method_config=method_config,
        live=True,
    )
    assert name == "test_spanish__baseline_long_explicit__live"


# ── Evaluation integration ──────────────────────────────────────────────────


def test_evaluate_sentences_stores_evaluations(session):
    """Run the full pipeline with evaluation and verify evaluation rows."""
    benchmark, constraint_sets = _create_test_benchmark(session)
    method_config = _create_test_method_config(session)

    experiment = Experiment(
        benchmark_id=benchmark.id,
        method_config_id=method_config.id,
        name="test_eval_run",
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

    evaluators = [ExpectedFormMatchEvaluator()]
    total = _evaluate_sentences(session, experiment, evaluators)

    assert total == 15  # 5 constraint sets x 3 sentences x 1 evaluator
    assert session.query(SentenceEvaluation).count() == 15

    for ev in session.query(SentenceEvaluation).all():
        assert ev.evaluator_name == "expected_form_match"
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
        session, sample_experiment, [ExpectedFormMatchEvaluator(), DummyEval()]
    )
    assert total == 2
    names = {e.evaluator_name for e in session.query(SentenceEvaluation).all()}
    assert names == {"expected_form_match", "dummy"}


def test_evaluate_no_sentences_produces_zero_evaluations(session, sample_experiment):
    """If the experiment has no sentences, evaluation produces nothing."""
    total = _evaluate_sentences(session, sample_experiment, [ExpectedFormMatchEvaluator()])
    assert total == 0
    assert session.query(SentenceEvaluation).count() == 0


def test_evaluate_sentences_idempotent(session, sample_constraint_set, sample_experiment):
    """Re-running evaluation replaces rows instead of duplicating them."""
    sent = GeneratedSentence(
        experiment_id=sample_experiment.id,
        constraint_set_id=sample_constraint_set.id,
        sentence="Nosotros comimos pizza.",
        translation="We ate pizza.",
        sample_index=0,
    )
    session.add(sent)
    session.commit()

    class MutableEval(BaseEvaluator):
        def __init__(self) -> None:
            self._calls = 0

        @property
        def name(self) -> str:
            return "mutable"

        def evaluate(self, sentence, translation, constraints):
            self._calls += 1
            score = 0.1 if self._calls == 1 else 0.9
            return EvaluationResult(score=score)

    ev = MutableEval()
    _evaluate_sentences(session, sample_experiment, [ev])
    _evaluate_sentences(session, sample_experiment, [ev])

    rows = session.query(SentenceEvaluation).all()
    assert len(rows) == 1
    assert rows[0].evaluator_name == "mutable"
    assert rows[0].score == 0.9


def test_evaluate_sentences_clear_scoped_to_experiment(
    session, sample_benchmark, sample_method_config, sample_constraint_set
):
    """Re-evaluating one experiment does not delete another experiment's evals."""
    exp_a = Experiment(
        benchmark_id=sample_benchmark.id,
        method_config_id=sample_method_config.id,
        name="exp_a",
        status="running",
    )
    exp_b = Experiment(
        benchmark_id=sample_benchmark.id,
        method_config_id=sample_method_config.id,
        name="exp_b",
        status="running",
    )
    session.add_all([exp_a, exp_b])
    session.flush()

    for exp in (exp_a, exp_b):
        session.add(
            GeneratedSentence(
                experiment_id=exp.id,
                constraint_set_id=sample_constraint_set.id,
                sentence="Hola.",
                translation="Hello.",
                sample_index=0,
            )
        )
    session.commit()

    _evaluate_sentences(session, exp_a, [ExpectedFormMatchEvaluator()])
    _evaluate_sentences(session, exp_b, [ExpectedFormMatchEvaluator()])
    assert session.query(SentenceEvaluation).count() == 2

    class HighScoreEval(BaseEvaluator):
        @property
        def name(self) -> str:
            return "high"

        def evaluate(self, sentence, translation, constraints):
            return EvaluationResult(score=1.0)

    _evaluate_sentences(session, exp_a, [HighScoreEval()])

    evals_a = (
        session.query(SentenceEvaluation)
        .join(GeneratedSentence)
        .filter(GeneratedSentence.experiment_id == exp_a.id)
        .all()
    )
    evals_b = (
        session.query(SentenceEvaluation)
        .join(GeneratedSentence)
        .filter(GeneratedSentence.experiment_id == exp_b.id)
        .all()
    )
    assert len(evals_a) == 1
    assert evals_a[0].evaluator_name == "high"
    assert evals_a[0].score == 1.0
    assert len(evals_b) == 1
    assert evals_b[0].evaluator_name == "expected_form_match"


def test_full_phase3_metrics_pipeline(session):
    """After generation + sentence eval: group metrics + roll-ups land in experiment_metrics."""
    benchmark, constraint_sets = _create_test_benchmark(session)
    method_config = _create_test_method_config(session)

    experiment = Experiment(
        benchmark_id=benchmark.id,
        method_config_id=method_config.id,
        name="phase3_integration",
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

    _evaluate_sentences(session, experiment, [ExpectedFormMatchEvaluator()])
    assert session.query(SentenceEvaluation).count() == 15

    g = _compute_and_store_group_metrics(session, experiment, DEFAULT_GROUP_METRICS)
    assert g == 54  # 9 metric types × (5 constraint_set + 1 experiment)

    r = aggregate_sentence_eval_rollups(session, experiment.id)
    assert r == 24  # 1 evaluator × 4 rollup kinds × (5 constraint_set + 1 experiment)

    assert session.query(ExperimentMetric).count() == 78  # 54 group + 24 roll-up
