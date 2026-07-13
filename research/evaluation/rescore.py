"""Re-run selected sentence evaluators on stored experiments (no regeneration)."""

from __future__ import annotations

from sqlalchemy.orm import joinedload

from research.db.models import Experiment, GeneratedSentence, SentenceEvaluation
from research.evaluation.distribution.lt_error_breakdown import LtErrorBreakdownMetric
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence.base import BaseEvaluator
from research.evaluation.sentence.fluency_perplexity import (
    EVALUATOR_NAME as PPL_EVALUATOR_NAME,
    FluencyPerplexityEvaluator,
)
from research.evaluation.sentence.languagetool import (
    EVALUATOR_NAME as GRAMMAR_EVALUATOR_NAME,
    LanguageToolGrammarEvaluator,
)
from research.evaluation.sentence.naturalness_llm_judge import (
    EVALUATOR_NAME as JUDGE_EVALUATOR_NAME,
    NaturalnessLlmJudgeEvaluator,
)
from research.pipeline import (
    _compute_and_store_group_metrics,
    _resolved_length_from_sentence,
)

DIAGNOSTIC_5_ARMS: dict[str, str] = {
    "5a": "diagnostic_5a_hf_qwen3_17b_n10",
    "5b": "diagnostic_5b_hf_qwen3_17b_n10",
    "5c": "diagnostic_5c_hf_qwen3_17b_n10",
}

DIAGNOSTIC_5_DB_FILES: dict[str, str] = {
    "5a": "diagnostic_5a.db",
    "5b": "diagnostic_5b.db",
    "5c": "diagnostic_5c.db",
}


def clear_sentence_evaluations_for_evaluator(
    session,
    experiment_id: int,
    evaluator_name: str,
) -> int:
    """Delete ``sentence_evaluations`` rows for one evaluator in an experiment."""
    sentence_ids = [
        row[0]
        for row in session.query(GeneratedSentence.id)
        .filter_by(experiment_id=experiment_id)
        .all()
    ]
    if not sentence_ids:
        return 0
    return session.query(SentenceEvaluation).filter(
        SentenceEvaluation.sentence_id.in_(sentence_ids),
        SentenceEvaluation.evaluator_name == evaluator_name,
    ).delete(synchronize_session="fetch")


def _split_existing_rows_for_resume(
    session,
    experiment_id: int,
    evaluator_name: str,
) -> tuple[set[int], list[int]]:
    """Partition existing rows into (sentence_ids to keep, row ids to delete).

    A row is kept when its details carry no ``error`` key; error rows
    (API/scorer failures stored as score 0.0) are deleted so resume re-runs
    them.
    """
    rows = (
        session.query(
            SentenceEvaluation.id,
            SentenceEvaluation.sentence_id,
            SentenceEvaluation.details,
        )
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == evaluator_name,
        )
        .all()
    )
    keep_sentence_ids: set[int] = set()
    error_row_ids: list[int] = []
    for row_id, sentence_id, details in rows:
        if isinstance(details, dict) and details.get("error"):
            error_row_ids.append(row_id)
        else:
            keep_sentence_ids.add(sentence_id)
    return keep_sentence_ids, error_row_ids


def rescore_evaluator_for_experiment(
    session,
    experiment: Experiment,
    evaluator: BaseEvaluator,
    *,
    commit_every: int = 500,
    resume: bool = False,
) -> int:
    """Re-run *evaluator* on stored sentences; leave other evaluators untouched.

    Default (``resume=False``): clear all existing rows for this evaluator
    and score every sentence.

    ``resume=True``: keep existing successful rows, delete rows whose details
    carry an ``error`` key, and only score sentences that now lack a row.
    Use after a crash or partial API failure — especially for the judge,
    where every call costs money.
    """
    skip_sentence_ids: set[int] = set()
    if resume:
        skip_sentence_ids, error_row_ids = _split_existing_rows_for_resume(
            session, experiment.id, evaluator.name
        )
        if error_row_ids:
            session.query(SentenceEvaluation).filter(
                SentenceEvaluation.id.in_(error_row_ids)
            ).delete(synchronize_session="fetch")
        session.commit()
        print(
            f"  Resume: keeping {len(skip_sentence_ids)} good {evaluator.name} rows, "
            f"deleted {len(error_row_ids)} error rows",
            flush=True,
        )
    else:
        removed = clear_sentence_evaluations_for_evaluator(
            session, experiment.id, evaluator.name
        )
        session.commit()
        print(
            f"  Cleared {removed} existing {evaluator.name} rows",
            flush=True,
        )

    sentences = (
        session.query(GeneratedSentence)
        .options(joinedload(GeneratedSentence.constraint_set))
        .filter_by(experiment_id=experiment.id)
        .order_by(GeneratedSentence.id)
        .all()
    )
    if skip_sentence_ids:
        sentences = [s for s in sentences if s.id not in skip_sentence_ids]
    total = len(sentences)
    if total == 0:
        print(f"  Nothing to score for {evaluator.name}", flush=True)
        return 0

    inserted = 0
    for idx, sent in enumerate(sentences, start=1):
        constraints = sent.constraint_set.to_constraints_dict()
        constraints["sentence_length"] = _resolved_length_from_sentence(sent)
        result = evaluator.evaluate(
            sentence=sent.sentence,
            translation=sent.translation,
            constraints=constraints,
        )
        session.add(
            SentenceEvaluation(
                sentence_id=sent.id,
                evaluator_name=evaluator.name,
                score=result.score,
                details=result.details,
            )
        )
        inserted += 1
        if idx % commit_every == 0:
            session.commit()
            print(
                f"  {evaluator.name}: {idx}/{total} sentences",
                flush=True,
            )
    session.commit()
    print(f"  Stored {inserted} {evaluator.name} evaluations", flush=True)
    return inserted


def rescore_grammar_languagetool(
    session,
    experiment: Experiment,
    *,
    evaluator: LanguageToolGrammarEvaluator | None = None,
    commit_every: int = 500,
    refresh_rollups: bool = True,
    refresh_lt_breakdown: bool = True,
) -> dict[str, int]:
    """Re-score grammar only, then refresh grammar roll-ups and LT breakdown metrics."""
    lt = evaluator or LanguageToolGrammarEvaluator()
    stats: dict[str, int] = {}
    stats["grammar_evals"] = rescore_evaluator_for_experiment(
        session,
        experiment,
        lt,
        commit_every=commit_every,
    )
    if refresh_rollups:
        print("  Refreshing sentence-eval roll-ups...", flush=True)
        stats["rollup_rows"] = aggregate_sentence_eval_rollups(session, experiment.id)
        print(f"  Stored {stats['rollup_rows']} rollup rows", flush=True)
    if refresh_lt_breakdown:
        lt_metrics = [
            LtErrorBreakdownMetric("constraint_set"),
            LtErrorBreakdownMetric("experiment"),
        ]
        print("  Refreshing lt_error_breakdown group metrics...", flush=True)
        stats["lt_breakdown_rows"] = _compute_and_store_group_metrics(
            session,
            experiment,
            lt_metrics,
        )
        print(
            f"  Stored {stats['lt_breakdown_rows']} lt_error_breakdown rows",
            flush=True,
        )
    return stats


def find_diagnostic_5_experiment(session, arm: str) -> Experiment:
    """Resolve the live Diagnostic 5 experiment for arm ``5a`` / ``5b`` / ``5c``."""
    key = arm.lower()
    method = DIAGNOSTIC_5_ARMS.get(key)
    if method is None:
        raise ValueError(
            f"Unknown arm {arm!r}; expected one of {sorted(DIAGNOSTIC_5_ARMS)}"
        )
    needle = f"__{method}__live"
    experiment = (
        session.query(Experiment)
        .filter(Experiment.name.like(f"%{needle}"))
        .order_by(Experiment.id.desc())
        .first()
    )
    if experiment is None:
        raise LookupError(
            f"No live Diagnostic 5 experiment matching {needle!r} in this database"
        )
    return experiment


def rescore_fluency_perplexity(
    session,
    experiment: Experiment,
    *,
    evaluator: FluencyPerplexityEvaluator | None = None,
    commit_every: int = 200,
    refresh_rollups: bool = True,
    resume: bool = False,
) -> dict[str, int]:
    """Re-score fluency_perplexity only; optionally refresh sentence-eval roll-ups."""
    ev = evaluator or FluencyPerplexityEvaluator()
    stats: dict[str, int] = {}
    stats["fluency_perplexity_evals"] = rescore_evaluator_for_experiment(
        session,
        experiment,
        ev,
        commit_every=commit_every,
        resume=resume,
    )
    if refresh_rollups:
        print("  Refreshing sentence-eval roll-ups...", flush=True)
        stats["rollup_rows"] = aggregate_sentence_eval_rollups(session, experiment.id)
        print(f"  Stored {stats['rollup_rows']} rollup rows", flush=True)
    return stats


def rescore_naturalness_judge(
    session,
    experiment: Experiment,
    *,
    evaluator: NaturalnessLlmJudgeEvaluator | None = None,
    commit_every: int = 50,
    refresh_rollups: bool = True,
    resume: bool = False,
) -> dict[str, int]:
    """Re-score naturalness_llm_judge only; optionally refresh sentence-eval roll-ups."""
    ev = evaluator or NaturalnessLlmJudgeEvaluator()
    stats: dict[str, int] = {}
    stats["naturalness_llm_judge_evals"] = rescore_evaluator_for_experiment(
        session,
        experiment,
        ev,
        commit_every=commit_every,
        resume=resume,
    )
    if refresh_rollups:
        print("  Refreshing sentence-eval roll-ups...", flush=True)
        stats["rollup_rows"] = aggregate_sentence_eval_rollups(session, experiment.id)
        print(f"  Stored {stats['rollup_rows']} rollup rows", flush=True)
    return stats


__all__ = [
    "DIAGNOSTIC_5_ARMS",
    "DIAGNOSTIC_5_DB_FILES",
    "GRAMMAR_EVALUATOR_NAME",
    "JUDGE_EVALUATOR_NAME",
    "PPL_EVALUATOR_NAME",
    "clear_sentence_evaluations_for_evaluator",
    "find_diagnostic_5_experiment",
    "rescore_evaluator_for_experiment",
    "rescore_fluency_perplexity",
    "rescore_grammar_languagetool",
    "rescore_naturalness_judge",
]
