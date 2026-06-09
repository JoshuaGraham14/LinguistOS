"""Uniqueness ratio: fraction of distinct target-language strings in a batch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


class UniquenessRatioMetric(BaseGroupMetric):
    """Distinct sentences / batch size (case-folded, trimmed)."""

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
