"""Evaluation layer.

- ``sentence/`` — per-output evaluators → ``sentence_evaluations``
- ``distribution/`` — joint metrics → ``experiment_metrics``
"""

from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.sentence import BaseEvaluator, EvaluationResult, GrammarEvaluator

__all__ = [
    "BaseEvaluator",
    "EvaluationResult",
    "GrammarEvaluator",
    "BaseGroupMetric",
    "GroupMetricResult",
    "DEFAULT_GROUP_METRICS",
]
