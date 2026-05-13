"""Abstract base class for sentence evaluators."""

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
    """Interface that every evaluator must implement.

    Subclasses provide a ``name`` and implement ``evaluate``, which receives
    the generated sentence text (target language) and the constraint metadata,
    and returns an ``EvaluationResult``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short unique identifier for this evaluator (stored in DB)."""

    @abstractmethod
    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        """Score a single generated sentence.

        Parameters
        ----------
        sentence:
            The generated target-language sentence.
        translation:
            The English translation produced alongside the sentence.
        constraints:
            Dict with keys like ``keyword``, ``tense``, ``person``, ``number``,
            ``target_language``, ``cefr_level``, etc.

        Returns
        -------
        EvaluationResult with a score in [0.0, 1.0] and optional details dict.
        """
