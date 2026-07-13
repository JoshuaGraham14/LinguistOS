"""Roll up per-sentence evaluations into experiment_metrics (Stage 2a)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from research.db.models import ExperimentMetric, GeneratedSentence, SentenceEvaluation

DEFAULT_PASS_THRESHOLD = 0.5

ROLLUP_PREFIXES = ("mean::", "min::", "std::", "pass_rate::", "errors_per_100w::")

# Detail axes rolled up from ``naturalness_llm_judge`` (kept on the native
# 1..5 Likert scale — distinct from ``mean::naturalness_llm_judge``, which
# averages the primary score ``naturalness / 5`` in [0, 1]).
JUDGE_DETAIL_AXES: tuple[str, ...] = (
    "grammaticality",
    "naturalness",
    "semantic_coherence",
)
JUDGE_EVALUATOR_NAME = "naturalness_llm_judge"


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


def _coerce_likert(value: Any) -> float | None:
    """Accept int/float Likert values in 1..5; reject everything else."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if 1.0 <= v <= 5.0:
            return v
    return None


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

    For ``naturalness_llm_judge``, also writes detail-axis roll-ups on the
    native 1..5 scale::

        mean::naturalness_llm_judge.grammaticality
        mean::naturalness_llm_judge.naturalness
        mean::naturalness_llm_judge.semantic_coherence

    (plus matching ``min::`` / ``std::``). Error rows (details.error set) and
    missing axes are skipped for those detail metrics.

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
            SentenceEvaluation.details,
        )
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(GeneratedSentence.experiment_id == experiment_id)
        .all()
    )
    if not rows:
        return 0

    by_cs: dict[tuple[str, int], list[float]] = defaultdict(list)
    by_evaluator: dict[str, list[float]] = defaultdict(list)
    density_cs: dict[tuple[str, int], tuple[int, int]] = defaultdict(lambda: (0, 0))
    density_evaluator: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    # (metric_suffix, cs_id) / metric_suffix → Likert values
    detail_cs: dict[tuple[str, int], list[float]] = defaultdict(list)
    detail_exp: dict[str, list[float]] = defaultdict(list)

    for evaluator_name, cs_id, score, details in rows:
        s = float(score)
        by_cs[(evaluator_name, int(cs_id))].append(s)
        by_evaluator[evaluator_name].append(s)

        if isinstance(details, dict):
            match_count = details.get("match_count")
            token_count = details.get("token_count")
            if isinstance(match_count, int) and isinstance(token_count, int):
                key = (evaluator_name, int(cs_id))
                m_sum, t_sum = density_cs[key]
                density_cs[key] = (m_sum + match_count, t_sum + token_count)
                e_sum, et_sum = density_evaluator[evaluator_name]
                density_evaluator[evaluator_name] = (
                    e_sum + match_count,
                    et_sum + token_count,
                )

            if (
                evaluator_name == JUDGE_EVALUATOR_NAME
                and not details.get("error")
            ):
                for axis in JUDGE_DETAIL_AXES:
                    likert = _coerce_likert(details.get(axis))
                    if likert is None:
                        continue
                    suffix = f"{JUDGE_EVALUATOR_NAME}.{axis}"
                    detail_cs[(suffix, int(cs_id))].append(likert)
                    detail_exp[suffix].append(likert)

    inserted = 0

    def _add_row(
        *,
        kind: str,
        metric_leaf: str,
        value: float,
        scope: str,
        constraint_set_id: int | None,
        count: int,
        extra_breakdown: dict[str, object] | None = None,
    ) -> None:
        nonlocal inserted
        breakdown: dict[str, object] = {
            "evaluator": metric_leaf.split(".", 1)[0],
            "count": count,
        }
        if "." in metric_leaf:
            breakdown["detail_axis"] = metric_leaf.split(".", 1)[1]
        if kind == "pass_rate":
            breakdown["pass_threshold"] = pass_threshold
        if extra_breakdown:
            breakdown.update(extra_breakdown)
        session.add(
            ExperimentMetric(
                experiment_id=experiment_id,
                metric_name=f"{kind}::{metric_leaf}",
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
                metric_leaf=evaluator_name,
                value=value,
                scope="constraint_set",
                constraint_set_id=cs_id,
                count=len(scores),
            )

    for evaluator_name, scores in by_evaluator.items():
        for kind, value in _stats(scores, pass_threshold).items():
            _add_row(
                kind=kind,
                metric_leaf=evaluator_name,
                value=value,
                scope="experiment",
                constraint_set_id=None,
                count=len(scores),
            )

    # Detail-axis roll-ups: mean/min/std only (pass_rate is not meaningful on
    # a 1..5 Likert with the default 0.5 threshold).
    for (suffix, cs_id), values in detail_cs.items():
        stats = _stats(values, pass_threshold)
        for kind in ("mean", "min", "std"):
            if kind not in stats:
                continue
            _add_row(
                kind=kind,
                metric_leaf=suffix,
                value=stats[kind],
                scope="constraint_set",
                constraint_set_id=cs_id,
                count=len(values),
                extra_breakdown={"scale": "1..5"},
            )

    for suffix, values in detail_exp.items():
        stats = _stats(values, pass_threshold)
        for kind in ("mean", "min", "std"):
            if kind not in stats:
                continue
            _add_row(
                kind=kind,
                metric_leaf=suffix,
                value=stats[kind],
                scope="experiment",
                constraint_set_id=None,
                count=len(values),
                extra_breakdown={"scale": "1..5"},
            )

    def _add_density_row(
        *,
        evaluator_name: str,
        match_sum: int,
        token_sum: int,
        scope: str,
        constraint_set_id: int | None,
        count: int,
    ) -> None:
        nonlocal inserted
        if token_sum <= 0:
            return
        value = 100.0 * match_sum / token_sum
        session.add(
            ExperimentMetric(
                experiment_id=experiment_id,
                metric_name=f"errors_per_100w::{evaluator_name}",
                value=round(value, 6),
                scope=scope,
                constraint_set_id=constraint_set_id,
                breakdown={
                    "evaluator": evaluator_name,
                    "count": count,
                    "match_sum": match_sum,
                    "token_sum": token_sum,
                },
            )
        )
        inserted += 1

    for (evaluator_name, cs_id), (match_sum, token_sum) in density_cs.items():
        _add_density_row(
            evaluator_name=evaluator_name,
            match_sum=match_sum,
            token_sum=token_sum,
            scope="constraint_set",
            constraint_set_id=cs_id,
            count=len(by_cs[(evaluator_name, cs_id)]),
        )

    for evaluator_name, (match_sum, token_sum) in density_evaluator.items():
        _add_density_row(
            evaluator_name=evaluator_name,
            match_sum=match_sum,
            token_sum=token_sum,
            scope="experiment",
            constraint_set_id=None,
            count=len(by_evaluator[evaluator_name]),
        )

    session.commit()
    return inserted
