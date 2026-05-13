"""Per-sentence evaluators: one ``BaseEvaluator`` subclass per module is typical."""

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.grammar import GrammarEvaluator

__all__ = ["BaseEvaluator", "EvaluationResult", "GrammarEvaluator"]
