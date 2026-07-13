"""Rescore wrappers write rows via the same code path as grammar rescoring."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("RESEARCH_DB", ":memory:")

from research.db.database import Base, SessionLocal, engine, init_db
from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    GeneratedSentence,
    MethodConfig,
    SentenceEvaluation,
)
from research.evaluation.rescore import (
    PPL_EVALUATOR_NAME,
    rescore_fluency_perplexity,
    rescore_naturalness_judge,
)
from research.evaluation.sentence.fluency_perplexity import (
    FluencyPerplexityEvaluator,
    PerplexityScorer,
)
from research.evaluation.sentence.naturalness_llm_judge import (
    EVALUATOR_NAME as JUDGE_EVALUATOR_NAME,
    LlmJudgeClient,
    NaturalnessLlmJudgeEvaluator,
)


class _StubPPL(PerplexityScorer):
    def __init__(self) -> None:
        self.model_id = "stub/ppl"
        self.dtype_name = "float32"
        self.revision = None
        self._device = "cpu"
        self.calls: list[str] = []

    def score(self, sentence: str) -> tuple[float, int]:
        self.calls.append(sentence)
        return 2.0, 5


class _StubJudge(LlmJudgeClient):
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def complete(self, system: str, user: str, *, model: str) -> str:
        self.calls.append({"user": user, "model": model})
        return (
            '{"grammaticality": 5, "naturalness": 4, '
            '"target_form_use": "correct_main_verb", '
            '"semantic_coherence": 5, "flags": [], '
            '"rationale": "The verb agrees with the subject and reads naturally."}'
        )


@pytest.fixture()
def rescore_env(tmp_path, monkeypatch):
    db_path = tmp_path / "rescore_test.db"
    monkeypatch.setenv("RESEARCH_DB", str(db_path))
    # Rebuild engine bindings against the temp path.
    from research.db import database as db_mod

    db_mod.engine.dispose()
    new_engine = db_mod.create_engine_for_path(db_path)
    db_mod.engine = new_engine
    db_mod.SessionLocal.configure(bind=new_engine)
    Base.metadata.drop_all(new_engine)
    Base.metadata.create_all(new_engine)

    session = SessionLocal()
    try:
        benchmark = Benchmark(
            name="rescore_test", language="es", mock_only=True
        )
        method = MethodConfig(
            name="rescore_test_method",
            method="baseline_gpt",
            samples_per_case=1,
            config={"model": "stub", "temperature": 0.0},
        )
        session.add_all([benchmark, method])
        session.flush()
        cs = ConstraintSet(
            benchmark_id=benchmark.id,
            keyword="comer",
            translation="to eat",
            expected_form="come",
            target_language="es",
            cefr_level="A1",
            constraints={
                "keyword": "comer",
                "tense": "present",
                "person": "3rd",
                "number": "singular",
                "target_language": "es",
                "expected_form": "come",
            },
        )
        session.add(cs)
        session.flush()
        experiment = Experiment(
            benchmark_id=benchmark.id,
            method_config_id=method.id,
            name="rescore_test__mock",
            status="completed",
        )
        session.add(experiment)
        session.flush()
        for i, text in enumerate(
            [
                "Ella come una manzana.",
                "Ellos comen fruta.",
                "Nosotros comemos temprano.",
            ]
        ):
            session.add(
                GeneratedSentence(
                    experiment_id=experiment.id,
                    constraint_set_id=cs.id,
                    sentence=text,
                    translation="They eat.",
                    sample_index=i,
                    generation_meta={"resolved_sentence_length": "short"},
                )
            )
        session.commit()
        yield session, experiment
    finally:
        session.close()


def _rows(session, experiment_id: int, evaluator_name: str) -> list[SentenceEvaluation]:
    return (
        session.query(SentenceEvaluation)
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == evaluator_name,
        )
        .all()
    )


def test_perplexity_rescore_writes_one_row_per_sentence(rescore_env):
    session, experiment = rescore_env
    scorer = _StubPPL()
    ev = FluencyPerplexityEvaluator(scorer=scorer)
    stats = rescore_fluency_perplexity(
        session,
        experiment,
        evaluator=ev,
        refresh_rollups=False,
    )
    assert stats["fluency_perplexity_evals"] == 3
    rows = _rows(session, experiment.id, PPL_EVALUATOR_NAME)
    assert len(rows) == 3
    for r in rows:
        assert 0.0 <= r.score <= 1.0
        assert r.details["model_id"] == "stub/ppl"
        assert r.details["token_count"] == 5
    assert scorer.calls == [
        "Ella come una manzana.",
        "Ellos comen fruta.",
        "Nosotros comemos temprano.",
    ]


def test_perplexity_rescore_is_idempotent(rescore_env):
    session, experiment = rescore_env
    ev = FluencyPerplexityEvaluator(scorer=_StubPPL())
    rescore_fluency_perplexity(session, experiment, evaluator=ev, refresh_rollups=False)
    rescore_fluency_perplexity(session, experiment, evaluator=ev, refresh_rollups=False)
    rows = _rows(session, experiment.id, PPL_EVALUATOR_NAME)
    assert len(rows) == 3


def test_resume_skips_good_rows_and_reruns_error_rows(rescore_env):
    session, experiment = rescore_env
    # First pass: score everything with a stub.
    first_scorer = _StubPPL()
    ev = FluencyPerplexityEvaluator(scorer=first_scorer)
    from research.evaluation.rescore import rescore_evaluator_for_experiment

    rescore_evaluator_for_experiment(session, experiment, ev)
    assert len(first_scorer.calls) == 3

    # Corrupt one row into an error row (simulates a mid-run API/scorer failure).
    rows = _rows(session, experiment.id, PPL_EVALUATOR_NAME)
    victim = rows[0]
    victim.details = {"error": "scorer_failure: simulated", "scorer_version": "v1"}
    victim.score = 0.0
    session.commit()
    error_sentence_id = victim.sentence_id

    # Resume: only the error row's sentence gets re-scored.
    second_scorer = _StubPPL()
    ev2 = FluencyPerplexityEvaluator(scorer=second_scorer)
    rescore_evaluator_for_experiment(session, experiment, ev2, resume=True)

    assert len(second_scorer.calls) == 1
    rows_after = _rows(session, experiment.id, PPL_EVALUATOR_NAME)
    assert len(rows_after) == 3
    # No error rows remain; the re-scored row belongs to the right sentence.
    for r in rows_after:
        assert not (r.details or {}).get("error")
    rescored = [r for r in rows_after if r.sentence_id == error_sentence_id]
    assert len(rescored) == 1
    assert rescored[0].details["model_id"] == "stub/ppl"


def test_resume_with_no_existing_rows_scores_everything(rescore_env):
    session, experiment = rescore_env
    scorer = _StubPPL()
    ev = FluencyPerplexityEvaluator(scorer=scorer)
    stats = rescore_fluency_perplexity(
        session, experiment, evaluator=ev, refresh_rollups=False, resume=True
    )
    assert stats["fluency_perplexity_evals"] == 3
    assert len(scorer.calls) == 3


def test_judge_rescore_writes_rows_and_preserves_flags(rescore_env):
    session, experiment = rescore_env
    client = _StubJudge()
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    stats = rescore_naturalness_judge(
        session,
        experiment,
        evaluator=ev,
        refresh_rollups=False,
    )
    assert stats["naturalness_llm_judge_evals"] == 3
    rows = _rows(session, experiment.id, JUDGE_EVALUATOR_NAME)
    assert len(rows) == 3
    for r in rows:
        assert r.score == pytest.approx(4 / 5)
        assert r.details["grammaticality"] == 5
        assert r.details["naturalness"] == 4
        assert r.details["target_form_use"] == "correct_main_verb"
        assert r.details["flags"] == []
        assert r.details["model_id"] == "gpt-5.4-mini"
    assert len(client.calls) == 3
