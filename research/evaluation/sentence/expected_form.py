"""Binary check: does the sentence contain the benchmark gold surface form?

Compares ``constraints["expected_form"]`` against whole tokens in the target
sentence (case-insensitive, punctuation-tolerant, accent-sensitive).
"""

from __future__ import annotations

import string
from typing import Any

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult

# Punctuation stripped from token edges before matching.
_EDGE_PUNCT = string.punctuation + "«»""''¡¿"


def tokenize(sentence: str) -> list[str]:
    """Split a sentence into word tokens with edge punctuation removed."""
    tokens: list[str] = []
    for raw in sentence.split():
        token = raw.strip(_EDGE_PUNCT)
        if token:
            tokens.append(token)
    return tokens


def normalize_token(token: str) -> str:
    """Case-fold a token for comparison; accents are preserved."""
    return token.casefold()


class ExpectedFormMatchEvaluator(BaseEvaluator):
    """Pass (1.0) when the exact expected surface form appears as a whole token."""

    @property
    def name(self) -> str:
        return "expected_form_match"

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        expected = (constraints.get("expected_form") or "").strip()
        if not expected:
            return EvaluationResult(
                score=0.0,
                details={
                    "passed": False,
                    "expected_form": None,
                    "matched_token": None,
                    "tokens_checked": 0,
                    "reason": "missing_expected_form",
                },
            )

        tokens = tokenize(sentence)
        expected_norm = normalize_token(expected)
        matched: str | None = None
        for token in tokens:
            if normalize_token(token) == expected_norm:
                matched = token
                break

        passed = matched is not None
        return EvaluationResult(
            score=1.0 if passed else 0.0,
            details={
                "passed": passed,
                "expected_form": expected,
                "matched_token": matched,
                "tokens_checked": len(tokens),
            },
        )
