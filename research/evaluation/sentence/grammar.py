"""Grammar-focused sentence evaluator stub (surface heuristics).

Replace or complement with spaCy/Stanza-backed evaluators in new modules under
``sentence/`` (e.g. ``sentence/tense_accuracy.py``).
"""

from __future__ import annotations

from typing import Any

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult


class GrammarEvaluator(BaseEvaluator):
    """Checks keyword stem presence, non-empty sentence and translation."""

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
