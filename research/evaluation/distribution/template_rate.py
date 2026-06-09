"""Template rate: fraction of sentences sharing the same opening token prefix."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.tokens import tokenize

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


class TemplateRateMetric(BaseGroupMetric):
    """Share of sentences whose first *k* tokens match at least one other sentence.

    Sentences shorter than *k* tokens use their full token list as the prefix.
    """

    def __init__(
        self,
        scope: Literal["constraint_set", "experiment"],
        *,
        k: int = 3,
    ) -> None:
        self._scope = scope
        self._k = k

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return (
            "template_rate"
            if self._scope == "constraint_set"
            else "template_rate_experiment"
        )

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        n = len(sentences)
        if n < 2:
            return GroupMetricResult(0.0, {"n": n, "k": self._k, "skipped": True})

        prefixes = [
            tuple(tokenize(s.sentence)[: self._k])
            for s in sentences
        ]
        counts = Counter(prefixes)
        templated = sum(1 for prefix in prefixes if counts[prefix] > 1)
        value = templated / n
        return GroupMetricResult(
            round(value, 4),
            {"n": n, "k": self._k, "templated": templated},
        )
