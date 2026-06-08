"""LanguageTool error category histogram (reads Stage 1 ``details``, no re-parse)."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.sentence.languagetool import EVALUATOR_NAME

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


def collect_lt_category_counts(sentences: list[GeneratedSentence]) -> dict[str, int]:
    """Aggregate filtered LT match categories from sentence evaluation rows."""
    counts: Counter[str] = Counter()
    for sent in sentences:
        for evaluation in sent.evaluations:
            if evaluation.evaluator_name != EVALUATOR_NAME:
                continue
            details = evaluation.details or {}
            for match in details.get("matches", []):
                category = match.get("category")
                if category:
                    counts[str(category)] += 1
    return dict(counts)


class LtErrorBreakdownMetric(BaseGroupMetric):
    """Histogram of ``grammar_languagetool`` error categories for a batch."""

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return (
            "lt_error_breakdown"
            if self._scope == "constraint_set"
            else "lt_error_breakdown_experiment"
        )

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        breakdown = collect_lt_category_counts(sentences)
        total = sum(breakdown.values())
        return GroupMetricResult(
            round(float(total), 4),
            breakdown,
        )
