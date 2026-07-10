"""Re-run selected sentence evaluators on stored experiments (no regeneration)."""

from __future__ import annotations

from sqlalchemy.orm import joinedload

from research.db.models import Experiment, GeneratedSentence, SentenceEvaluation
from research.evaluation.distribution.lt_error_breakdown import LtErrorBreakdownMetric
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence.base import BaseEvaluator
from research.evaluation.sentence.languagetool import (
    EVALUATOR_NAME as GRAMMAR_EVALUATOR_NAME,
    LanguageToolGrammarEvaluator,
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


def rescore_evaluator_for_experiment(
    session,
    experiment: Experiment,
    evaluator: BaseEvaluator,
    *,
    commit_every: int = 500,
) -> int:
    """Re-run *evaluator* on every stored sentence; leave other evaluators untouched."""
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
    total = len(sentences)
    if total == 0:
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


__all__ = [
    "DIAGNOSTIC_5_ARMS",
    "DIAGNOSTIC_5_DB_FILES",
    "GRAMMAR_EVALUATOR_NAME",
    "clear_sentence_evaluations_for_evaluator",
    "find_diagnostic_5_experiment",
    "rescore_evaluator_for_experiment",
    "rescore_grammar_languagetool",
]
