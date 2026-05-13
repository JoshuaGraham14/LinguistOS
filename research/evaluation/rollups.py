"""Roll up per-sentence evaluations into experiment_metrics (Stage 2a)."""

from __future__ import annotations

from sqlalchemy import func

from research.db.models import ExperimentMetric, GeneratedSentence, SentenceEvaluation


def aggregate_sentence_eval_rollups(session, experiment_id: int) -> int:
    """Insert experiment_metrics rows: mean score per evaluator (overall + per constraint set).

    Metric names are ``mean::<evaluator_name>``. Scope is ``experiment`` for the overall
    mean (``constraint_set_id`` NULL) and ``constraint_set`` for per-set means.

    Idempotent: any existing ``mean::*`` rows for this experiment are deleted first.

    Returns the number of metric rows inserted.
    """
    session.query(ExperimentMetric).filter(
        ExperimentMetric.experiment_id == experiment_id,
        ExperimentMetric.metric_name.like("mean::%"),
    ).delete(synchronize_session="fetch")

    q = (
        session.query(
            SentenceEvaluation.evaluator_name,
            GeneratedSentence.constraint_set_id,
            func.avg(SentenceEvaluation.score).label("avg_score"),
            func.count(SentenceEvaluation.id).label("cnt"),
        )
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(GeneratedSentence.experiment_id == experiment_id)
        .group_by(SentenceEvaluation.evaluator_name, GeneratedSentence.constraint_set_id)
    )

    per_cs_rows = list(q.all())
    if not per_cs_rows:
        return 0

    inserted = 0
    totals: dict[str, tuple[float, int]] = {}

    for evaluator_name, cs_id, avg_score, cnt in per_cs_rows:
        avg_f = float(avg_score)
        n = int(cnt)
        session.add(
            ExperimentMetric(
                experiment_id=experiment_id,
                metric_name=f"mean::{evaluator_name}",
                value=round(avg_f, 6),
                scope="constraint_set",
                constraint_set_id=int(cs_id),
                breakdown={"evaluator": evaluator_name, "count": n},
            )
        )
        inserted += 1
        acc_sum, acc_n = totals.get(evaluator_name, (0.0, 0))
        totals[evaluator_name] = (acc_sum + avg_f * n, acc_n + n)

    for evaluator_name, (sum_scores, total_n) in totals.items():
        mean_overall = sum_scores / total_n if total_n else 0.0
        session.add(
            ExperimentMetric(
                experiment_id=experiment_id,
                metric_name=f"mean::{evaluator_name}",
                value=round(mean_overall, 6),
                scope="experiment",
                constraint_set_id=None,
                breakdown={"evaluator": evaluator_name, "count": total_n},
            )
        )
        inserted += 1

    session.commit()
    return inserted
