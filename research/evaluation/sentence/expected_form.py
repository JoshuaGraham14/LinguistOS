"""Binary check: does the sentence contain the benchmark gold surface form?

Compares ``constraints["expected_form"]`` against whole tokens in the target
sentence (case-insensitive, punctuation-tolerant, accent-sensitive).

Optional Welsh / multi-piece extensions (backward compatible):

- ``expected_form_alts``: ``|``-separated alternatives; any one match counts
  for the primary form.
- ``expected_aux`` / ``expected_aux_alts``: companion auxiliary that must also
  appear (periphrastic constructions).
- ``particle``: optional particle token that must also appear (e.g. Welsh *yn*).
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


def _split_alts(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [p.strip() for p in text.split("|") if p.strip()]


def _match_any(tokens: list[str], candidates: list[str]) -> str | None:
    if not candidates:
        return None
    wanted = {normalize_token(c) for c in candidates}
    for token in tokens:
        if normalize_token(token) in wanted:
            return token
    return None


class ExpectedFormMatchEvaluator(BaseEvaluator):
    """Pass (1.0) when the expected surface form(s) appear as whole tokens."""

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
                    "matched_aux": None,
                    "matched_particle": None,
                    "tokens_checked": 0,
                    "reason": "missing_expected_form",
                },
            )

        tokens = tokenize(sentence)
        primary_candidates = [expected, *_split_alts(constraints.get("expected_form_alts"))]
        matched = _match_any(tokens, primary_candidates)

        matched_aux: str | None = None
        aux = (constraints.get("expected_aux") or "").strip()
        aux_ok = True
        if aux:
            aux_candidates = [aux, *_split_alts(constraints.get("expected_aux_alts"))]
            matched_aux = _match_any(tokens, aux_candidates)
            aux_ok = matched_aux is not None

        matched_particle: str | None = None
        particle = (constraints.get("particle") or "").strip()
        particle_ok = True
        if particle:
            matched_particle = _match_any(tokens, [particle])
            particle_ok = matched_particle is not None

        passed = matched is not None and aux_ok and particle_ok
        reason = None
        if not passed:
            if matched is None:
                reason = "missing_expected_form_token"
            elif not aux_ok:
                reason = "missing_expected_aux"
            elif not particle_ok:
                reason = "missing_particle"

        return EvaluationResult(
            score=1.0 if passed else 0.0,
            details={
                "passed": passed,
                "expected_form": expected,
                "expected_aux": aux or None,
                "particle": particle or None,
                "matched_token": matched,
                "matched_aux": matched_aux,
                "matched_particle": matched_particle,
                "tokens_checked": len(tokens),
                **({"reason": reason} if reason else {}),
            },
        )
