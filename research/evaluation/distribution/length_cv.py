"""Coefficient of variation of token counts within a batch."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.tokens import tokenize

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


class LengthCvMetric(BaseGroupMetric):
    """Population CV of token counts (std / mean). Zero when mean is 0 or n < 2."""

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return "length_cv" if self._scope == "constraint_set" else "length_cv_experiment"

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        if not sentences:
            return GroupMetricResult(0.0, {"n": 0, "counts": []})

        counts = [len(tokenize(s.sentence)) for s in sentences]
        n = len(counts)
        mean = sum(counts) / n
        if mean == 0 or n < 2:
            return GroupMetricResult(
                0.0,
                {"n": n, "counts": counts, "mean": round(mean, 4), "std": 0.0},
            )

        variance = sum((c - mean) ** 2 for c in counts) / n
        std = math.sqrt(variance)
        cv = std / mean
        return GroupMetricResult(
            round(cv, 4),
            {
                "n": n,
                "counts": counts,
                "mean": round(mean, 4),
                "std": round(std, 4),
            },
        )
