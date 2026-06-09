"""Distinct-n: unique n-grams / total n-grams pooled across a batch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.distribution.tokens import tokenize

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


class DistinctNgramMetric(BaseGroupMetric):
    """Distinct-n over all sentences in the batch (higher = more diverse)."""

    def __init__(self, n: int, scope: Literal["constraint_set", "experiment"]) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        self._n = n
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        suffix = "_experiment" if self._scope == "experiment" else ""
        return f"distinct_{self._n}{suffix}"

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        if not sentences:
            return GroupMetricResult(0.0, {"n": 0, "unique": 0, "total": 0, "ngram_n": self._n})

        all_ngrams: list[tuple[str, ...]] = []
        for sentence in sentences:
            all_ngrams.extend(_ngrams(tokenize(sentence.sentence), self._n))

        total = len(all_ngrams)
        if total == 0:
            return GroupMetricResult(0.0, {"n": len(sentences), "unique": 0, "total": 0, "ngram_n": self._n})

        unique = len(set(all_ngrams))
        value = unique / total
        return GroupMetricResult(
            round(value, 4),
            {"n": len(sentences), "unique": unique, "total": total, "ngram_n": self._n},
        )
