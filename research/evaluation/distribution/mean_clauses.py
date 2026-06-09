"""Mean clausal count from ``clause_count`` sentence evaluation rows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult
from research.evaluation.sentence.clause_count import EVALUATOR_NAME

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence


def collect_clause_counts(sentences: list[GeneratedSentence]) -> list[int]:
    """Extract integer clause counts from stored evaluation details."""
    counts: list[int] = []
    for sent in sentences:
        for evaluation in sent.evaluations:
            if evaluation.evaluator_name != EVALUATOR_NAME:
                continue
            details = evaluation.details or {}
            raw = details.get("clause_count")
            if isinstance(raw, int):
                counts.append(raw)
            break
    return counts


class MeanClausesMetric(BaseGroupMetric):
    """Average raw ``clause_count`` across sentences (requires Stage 1 eval rows)."""

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return "mean_clauses" if self._scope == "constraint_set" else "mean_clauses_experiment"

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        counts = collect_clause_counts(sentences)
        if not counts:
            return GroupMetricResult(0.0, {"n": 0, "counts": []})

        mean = sum(counts) / len(counts)
        return GroupMetricResult(
            round(mean, 4),
            {"n": len(counts), "counts": counts, "mean": round(mean, 4)},
        )
