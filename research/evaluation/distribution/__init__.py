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

__all__ = [
    "DEFAULT_GROUP_METRICS",
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
