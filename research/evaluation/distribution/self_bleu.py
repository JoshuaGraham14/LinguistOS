"""Self-BLEU: mean sentence-level BLEU of each sentence against the rest of the batch."""

from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING, Literal

from sacrebleu.metrics import BLEU

from research.evaluation.distribution.base import BaseGroupMetric, GroupMetricResult

if TYPE_CHECKING:
    from research.db.models import GeneratedSentence

_BLEU = BLEU(tokenize="intl", effective_order=True, smooth_method="exp")

# Experiment-wide Self-BLEU is O(n²); cap subsampling for large runs (e.g. n=150).
_DEFAULT_EXPERIMENT_CAP = 500


def _experiment_self_bleu_cap() -> int:
    raw = os.environ.get("SELF_BLEU_EXPERIMENT_CAP", str(_DEFAULT_EXPERIMENT_CAP))
    try:
        return max(2, int(raw))
    except ValueError:
        return _DEFAULT_EXPERIMENT_CAP


class SelfBleuMetric(BaseGroupMetric):
    """Mean sacrebleu sentence BLEU of each sentence vs all others in the batch.

    Lower values indicate more diverse output. Uses smoothed BLEU with
    ``effective_order=True`` so short practice sentences (2–6 tokens) still
    receive meaningful scores.
    """

    def __init__(self, scope: Literal["constraint_set", "experiment"]) -> None:
        self._scope = scope

    @property
    def scope(self) -> Literal["constraint_set", "experiment"]:
        return self._scope

    @property
    def name(self) -> str:
        return "self_bleu" if self._scope == "constraint_set" else "self_bleu_experiment"

    def compute(self, sentences: list[GeneratedSentence]) -> GroupMetricResult:
        n = len(sentences)
        if n < 2:
            return GroupMetricResult(0.0, {"n": n, "skipped": True})

        texts = [s.sentence.strip() for s in sentences if s.sentence.strip()]
        if len(texts) < 2:
            return GroupMetricResult(0.0, {"n": n, "skipped": True})

        details: dict[str, object] = {"n": len(texts)}
        if self._scope == "experiment" and len(texts) > _experiment_self_bleu_cap():
            cap = _experiment_self_bleu_cap()
            texts = random.Random(0).sample(texts, cap)
            details["sampled"] = True
            details["sample_n"] = cap
            details["pool_n"] = n

        scores: list[float] = []
        for i, hypothesis in enumerate(texts):
            references = [texts[j] for j in range(len(texts)) if j != i]
            bleu_score = _BLEU.sentence_score(hypothesis, references).score / 100.0
            scores.append(bleu_score)

        mean_score = sum(scores) / len(scores)
        details["mean"] = round(mean_score, 4)
        return GroupMetricResult(
            round(mean_score, 4),
            details,
        )
