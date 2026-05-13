"""Stub grammar evaluator -- placeholder for Phase 2.

Returns a heuristic score based on simple surface checks.  A real grammar
evaluator (spaCy / Stanza morphological analysis) will replace this later.
"""

from __future__ import annotations

from typing import Any

from research.evaluation.base import BaseEvaluator, EvaluationResult


class GrammarEvaluator(BaseEvaluator):
    """Placeholder evaluator that checks whether the keyword appears in the sentence."""

    @property
    def name(self) -> str:
        return "grammar_stub"

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        keyword = constraints.get("keyword", "")
        stem = keyword[:3] if len(keyword) >= 3 else keyword

        has_keyword = stem.lower() in sentence.lower()
        has_translation = bool(translation.strip())
        is_nonempty = bool(sentence.strip())

        checks = {
            "has_keyword_stem": has_keyword,
            "has_translation": has_translation,
            "is_nonempty": is_nonempty,
        }

        passed = sum(checks.values())
        score = passed / len(checks)

        return EvaluationResult(score=round(score, 4), details=checks)
