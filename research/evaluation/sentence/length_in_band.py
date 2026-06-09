"""Binary check: token count within the requested sentence_length band."""

from __future__ import annotations

from typing import Any

from research.evaluation.distribution.tokens import tokenize as count_tokens
from research.evaluation.length_bands import get_band, token_count_in_band
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult


class LengthInBandEvaluator(BaseEvaluator):
    """Pass (1.0) when whitespace-token count is within the target band."""

    @property
    def name(self) -> str:
        return "length_in_band"

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        sentence_length = (constraints.get("sentence_length") or "short").strip()
        try:
            lo, hi = get_band(sentence_length)
        except ValueError as exc:
            return EvaluationResult(
                score=0.0,
                details={
                    "in_band": False,
                    "reason": "unknown_sentence_length",
                    "sentence_length": sentence_length,
                    "error": str(exc),
                },
            )

        tokens = count_tokens(sentence)
        count = len(tokens)
        in_band = token_count_in_band(count, sentence_length)
        return EvaluationResult(
            score=1.0 if in_band else 0.0,
            details={
                "in_band": in_band,
                "token_count": count,
                "target_length": sentence_length,
                "min": lo,
                "max": hi,
            },
        )
