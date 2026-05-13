"""Shared interface for distribution / joint metrics (batch-level).

Concrete metrics live in separate modules (e.g. ``uniqueness.py``). Outputs are stored
only in ``experiment_metrics``, never in ``sentence_evaluations``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


@dataclass
class GroupMetricResult:
    """Single numeric value plus optional diagnostic breakdown."""

    value: float
    details: dict | None = None


class BaseGroupMetric(ABC):
    """Metric computed jointly over a list of ``GeneratedSentence`` rows.

    ``scope`` controls storage: ``constraint_set`` = one value per morpho-syntactic
    bucket within an experiment; ``experiment`` = one value pooled over the whole run.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stored as ``experiment_metrics.metric_name``."""

    @property
    @abstractmethod
    def scope(self) -> Literal["constraint_set", "experiment"]:
        ...

    @abstractmethod
    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        ...
