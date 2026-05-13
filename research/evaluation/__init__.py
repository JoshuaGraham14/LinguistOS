"""Evaluation layer.

- ``sentence/`` — per-output evaluators → ``sentence_evaluations``
- ``distribution/`` — joint metrics → ``experiment_metrics``
- ``rollups.py`` — aggregate sentence scores → ``experiment_metrics``
"""

from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence import BaseEvaluator, EvaluationResult, GrammarEvaluator

__all__ = [
    "BaseEvaluator",
    "EvaluationResult",
    "GrammarEvaluator",
    "BaseGroupMetric",
    "GroupMetricResult",
    "DEFAULT_GROUP_METRICS",
    "aggregate_sentence_eval_rollups",
]
