"""Distribution-level (group) metrics: computed over many samples, stored in experiment_metrics."""

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
    """Metric computed over a list of generated sentences.

    ``scope`` is ``constraint_set`` when ``compute`` receives only rows sharing one
    ``constraint_set_id``, or ``experiment`` when it receives all sentences in the run.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stored as experiment_metrics.metric_name."""

    @property
    @abstractmethod
    def scope(self) -> Literal["constraint_set", "experiment"]:
        """Whether this metric is stored per constraint set or once per experiment."""

    @abstractmethod
    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        ...


class UniquenessRatioMetric(BaseGroupMetric):
    """Stub diversity metric: fraction of distinct sentences (case-folded, trimmed).

    Real diversity (self-BLEU, embedding variance, etc.) plugs in as another
    ``BaseGroupMetric`` implementation.
    """

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return (
            "uniqueness_ratio"
            if self._scope == "constraint_set"
            else "uniqueness_ratio_experiment"
        )

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        if not sentences:
            return GroupMetricResult(0.0, {"unique": 0, "n": 0})
        texts = [s.sentence.strip().lower() for s in sentences]
        unique = len(set(texts))
        n = len(texts)
        return GroupMetricResult(
            round(unique / n, 4),
            {"unique": unique, "n": n},
        )


DEFAULT_GROUP_METRICS: list[BaseGroupMetric] = [
    UniquenessRatioMetric("constraint_set"),
    UniquenessRatioMetric("experiment"),
]
