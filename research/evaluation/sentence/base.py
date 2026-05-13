"""Shared interface for per-sentence evaluation.

Each concrete evaluator lives in its own module under ``sentence/`` and writes rows to
``sentence_evaluations`` (no schema change when adding a new evaluator).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationResult:
    """The output of a single evaluation: a numeric score plus optional details."""

    score: float
    details: dict[str, Any] | None = None


class BaseEvaluator(ABC):
    """Interface every **sentence-level** evaluator implements.

    Subclasses provide ``name`` and ``evaluate``, returning ``EvaluationResult``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier stored in ``sentence_evaluations.evaluator_name``."""

    @abstractmethod
    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        """Score one generated sentence.

        ``constraints`` includes keyword, tense, person, number, target_language,
        cefr_level, etc.
        """
