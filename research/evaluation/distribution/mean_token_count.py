"""Mean token count per sentence in a batch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.tokens import tokenize

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


class MeanTokenCountMetric(BaseGroupMetric):
    """Average whitespace-token count across sentences."""

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return (
            "mean_token_count"
            if self._scope == "constraint_set"
            else "mean_token_count_experiment"
        )

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        if not sentences:
            return GroupMetricResult(0.0, {"n": 0, "counts": []})

        counts = [len(tokenize(s.sentence)) for s in sentences]
        mean = sum(counts) / len(counts)
        return GroupMetricResult(
            round(mean, 4),
            {"n": len(counts), "counts": counts, "mean": round(mean, 4)},
        )
