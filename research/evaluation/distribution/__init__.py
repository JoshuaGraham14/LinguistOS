"""Distribution metrics registry — extend ``DEFAULT_GROUP_METRICS`` when adding modules."""

from __future__ import annotations

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.distinct_ngram import DistinctNgramMetric
from research.evaluation.distribution.length_cv import LengthCvMetric
from research.evaluation.distribution.lt_error_breakdown import LtErrorBreakdownMetric
from research.evaluation.distribution.mean_clauses import MeanClausesMetric
from research.evaluation.distribution.mean_token_count import MeanTokenCountMetric
from research.evaluation.distribution.self_bleu import SelfBleuMetric
from research.evaluation.distribution.template_rate import TemplateRateMetric
from research.evaluation.distribution.uniqueness import UniquenessRatioMetric

DEFAULT_GROUP_METRICS: list[BaseGroupMetric] = [
    UniquenessRatioMetric("constraint_set"),
    UniquenessRatioMetric("experiment"),
    SelfBleuMetric("constraint_set"),
    SelfBleuMetric("experiment"),
    TemplateRateMetric("constraint_set"),
    TemplateRateMetric("experiment"),
    DistinctNgramMetric(1, "constraint_set"),
    DistinctNgramMetric(1, "experiment"),
    DistinctNgramMetric(2, "constraint_set"),
    DistinctNgramMetric(2, "experiment"),
    MeanTokenCountMetric("constraint_set"),
    MeanTokenCountMetric("experiment"),
    LengthCvMetric("constraint_set"),
    LengthCvMetric("experiment"),
    MeanClausesMetric("constraint_set"),
    MeanClausesMetric("experiment"),
    LtErrorBreakdownMetric("constraint_set"),
    LtErrorBreakdownMetric("experiment"),
]

EXPERIMENT_GROUP_METRIC_NAMES: tuple[str, ...] = tuple(
    m.name for m in DEFAULT_GROUP_METRICS if m.scope == "experiment"
)


def group_metrics_for_run(*, include_experiment_scope: bool = True) -> list[BaseGroupMetric]:
    """Return group metrics to compute for a run.

    Large multi-cell benchmarks should often set ``include_experiment_scope=False``
    to skip pooled metrics (especially experiment-wide Self-BLEU).
    """
    if include_experiment_scope:
        return list(DEFAULT_GROUP_METRICS)
    return [m for m in DEFAULT_GROUP_METRICS if m.scope == "constraint_set"]


__all__ = [
    "DEFAULT_GROUP_METRICS",
    "EXPERIMENT_GROUP_METRIC_NAMES",
    "group_metrics_for_run",
    "BaseGroupMetric",
    "DistinctNgramMetric",
    "GroupMetricResult",
    "LengthCvMetric",
    "LtErrorBreakdownMetric",
    "MeanClausesMetric",
    "MeanTokenCountMetric",
    "SelfBleuMetric",
    "TemplateRateMetric",
    "UniquenessRatioMetric",
]
