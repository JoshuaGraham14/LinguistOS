"""Distribution metrics registry — extend ``DEFAULT_GROUP_METRICS`` when adding modules."""

from __future__ import annotations

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.uniqueness import UniquenessRatioMetric

DEFAULT_GROUP_METRICS: list[BaseGroupMetric] = [
    UniquenessRatioMetric("constraint_set"),
    UniquenessRatioMetric("experiment"),
]

__all__ = [
    "DEFAULT_GROUP_METRICS",
    "BaseGroupMetric",
    "GroupMetricResult",
    "UniquenessRatioMetric",
]
