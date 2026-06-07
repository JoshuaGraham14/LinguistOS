"""Per-sentence evaluators: one ``BaseEvaluator`` subclass per module is typical."""

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.grammar import GrammarEvaluator
from research.evaluation.sentence.verb_morphology import VerbMorphologyEvaluator

DEFAULT_EVALUATORS: list[BaseEvaluator] = [
    GrammarEvaluator(),
    ExpectedFormMatchEvaluator(),
    VerbMorphologyEvaluator(),
]

__all__ = [
    "BaseEvaluator",
    "EvaluationResult",
    "ExpectedFormMatchEvaluator",
    "GrammarEvaluator",
    "VerbMorphologyEvaluator",
    "DEFAULT_EVALUATORS",
]
