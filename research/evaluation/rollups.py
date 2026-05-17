"""Roll up per-sentence evaluations into experiment_metrics (Stage 2a)."""

from __future__ import annotations

import math
from collections import defaultdict

from research.db.models import ExperimentMetric, GeneratedSentence, SentenceEvaluation

DEFAULT_PASS_THRESHOLD = 0.5

ROLLUP_PREFIXES = ("mean::", "min::", "std::", "pass_rate::")


def _stats(scores: list[float], pass_threshold: float) -> dict[str, float]:
    """Population mean, min, std, and pass rate for a list of scores."""
    n = len(scores)
    if n == 0:
        return {}
    mean = sum(scores) / n
    mn = min(scores)
    if n == 1:
        std = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in scores) / n
        std = math.sqrt(variance)
    passes = sum(1 for x in scores if x >= pass_threshold)
    return {
        "mean": mean,
        "min": mn,
        "std": std,
        "pass_rate": passes / n,
    }


def aggregate_sentence_eval_rollups(
    session,
    experiment_id: int,
    *,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> int:
    """Insert experiment_metrics: mean, min, std, pass_rate per evaluator.

    Metric names are ``<kind>::<evaluator_name>`` for kind in mean, min, std,
    pass_rate. Scope is ``experiment`` for pooled stats (``constraint_set_id``
    NULL) and ``constraint_set`` for per-set stats.

    Idempotent: existing rollup rows (any of the prefixes above) for this
    experiment are deleted first.

    Returns the number of metric rows inserted.
    """
    for prefix in ROLLUP_PREFIXES:
        session.query(ExperimentMetric).filter(
            ExperimentMetric.experiment_id == experiment_id,
            ExperimentMetric.metric_name.like(f"{prefix}%"),
        ).delete(synchronize_session="fetch")

    rows = (
        session.query(
            SentenceEvaluation.evaluator_name,
            GeneratedSentence.constraint_set_id,
            SentenceEvaluation.score,
        )
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(GeneratedSentence.experiment_id == experiment_id)
        .all()
    )
    if not rows:
        return 0

    by_cs: dict[tuple[str, int], list[float]] = defaultdict(list)
    by_evaluator: dict[str, list[float]] = defaultdict(list)

    for evaluator_name, cs_id, score in rows:
        s = float(score)
        by_cs[(evaluator_name, int(cs_id))].append(s)
        by_evaluator[evaluator_name].append(s)

    inserted = 0

    def _add_row(
        *,
        kind: str,
        evaluator_name: str,
        value: float,
        scope: str,
        constraint_set_id: int | None,
        count: int,
    ) -> None:
        nonlocal inserted
        breakdown: dict[str, object] = {
            "evaluator": evaluator_name,
            "count": count,
        }
        if kind == "pass_rate":
            breakdown["pass_threshold"] = pass_threshold
        session.add(
            ExperimentMetric(
                experiment_id=experiment_id,
                metric_name=f"{kind}::{evaluator_name}",
                value=round(value, 6),
                scope=scope,
                constraint_set_id=constraint_set_id,
                breakdown=breakdown,
            )
        )
        inserted += 1

    for (evaluator_name, cs_id), scores in by_cs.items():
        for kind, value in _stats(scores, pass_threshold).items():
            _add_row(
                kind=kind,
                evaluator_name=evaluator_name,
                value=value,
                scope="constraint_set",
                constraint_set_id=cs_id,
                count=len(scores),
            )

    for evaluator_name, scores in by_evaluator.items():
        for kind, value in _stats(scores, pass_threshold).items():
            _add_row(
                kind=kind,
                evaluator_name=evaluator_name,
                value=value,
                scope="experiment",
                constraint_set_id=None,
                count=len(scores),
            )

    session.commit()
    return inserted
