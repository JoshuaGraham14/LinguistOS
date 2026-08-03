"""Grammar check via LanguageTool (rule-based, independent of spaCy).

Binary pass when no filtered rule matches fire. Rich ``details`` feed Stage 2a
roll-ups (EFSR, errors/100w) and Stage 2b ``lt_error_breakdown``.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.expected_form import tokenize

# Categories counted as grammar slips for this thesis (exclude accents/casing/style).
GRAMMAR_CATEGORIES: frozenset[str] = frozenset(
    {
        "AGREEMENT_VERBS",
        "AGREEMENT_NOUNS",
        "GRAMMAR",
        "MISSPELLING",
        "CONFUSIONS",  # e.g. al + feminine noun (al tienda → a la tienda)
    }
)

# LanguageTool has no Welsh grammar data. Prefer omitting via
# ``default_evaluators_for_language("cy")``; this guard avoids accidental
# Spanish-rule scoring if the evaluator is still invoked on Welsh text.
UNSUPPORTED_LANGUAGETOOL_LANGS: frozenset[str] = frozenset({"cy"})

_LT_CACHE: dict[str, Any] = {}
_LT_INIT_ERRORS: dict[str, str] = {}


class LanguageToolLike(Protocol):
    def check(self, text: str) -> list[Any]: ...


def _get_languagetool(language: str) -> LanguageToolLike:
    """Lazy-load and cache a LanguageTool server for *language*."""
    if language in _LT_CACHE:
        return _LT_CACHE[language]
    if language in _LT_INIT_ERRORS:
        raise RuntimeError(_LT_INIT_ERRORS[language])
    import language_tool_python

    try:
        tool = language_tool_python.LanguageTool(language)
    except Exception as exc:  # pragma: no cover - environment-dependent
        _LT_INIT_ERRORS[language] = str(exc)
        raise
    _LT_CACHE[language] = tool
    return tool


def filter_grammar_matches(matches: list[Any]) -> list[Any]:
    """Keep only matches in ``GRAMMAR_CATEGORIES``."""
    return [m for m in matches if getattr(m, "category", None) in GRAMMAR_CATEGORIES]


def match_to_dict(match: Any) -> dict[str, Any]:
    """Serialize one LanguageTool ``Match`` for ``details`` storage."""
    replacements = getattr(match, "replacements", None) or []
    return {
        "rule": match.rule_id,
        "category": match.category,
        "message": match.message,
        "offset": match.offset,
        "error_length": match.error_length,
        "replacements": list(replacements)[:3],
    }


def build_languagetool_details(
    *,
    sentence: str,
    all_matches: list[Any],
    grammar_matches: list[Any],
    error: str | None = None,
) -> dict[str, Any]:
    """Build the ``details`` payload stored on ``sentence_evaluations``."""
    if error is not None:
        return {
            "passed": False,
            "match_count": 0,
            "total_match_count": 0,
            "token_count": len(tokenize(sentence)),
            "matches": [],
            "error": error,
        }
    return {
        "passed": len(grammar_matches) == 0,
        "match_count": len(grammar_matches),
        "total_match_count": len(all_matches),
        "token_count": len(tokenize(sentence)),
        "matches": [match_to_dict(m) for m in grammar_matches],
    }


EVALUATOR_NAME = "grammar_languagetool"


class LanguageToolGrammarEvaluator(BaseEvaluator):
    """Pass (1.0) when LanguageTool reports no grammar-category violations."""

    def __init__(
        self,
        tool_factory: Callable[[str], LanguageToolLike] | None = None,
    ) -> None:
        self._tool_factory = tool_factory or _get_languagetool

    @property
    def name(self) -> str:
        return EVALUATOR_NAME

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        language = (constraints.get("target_language") or "es").strip() or "es"
        if language in UNSUPPORTED_LANGUAGETOOL_LANGS:
            return EvaluationResult(
                score=0.0,
                details={
                    "passed": False,
                    "match_count": 0,
                    "total_match_count": 0,
                    "token_count": len(tokenize(sentence)),
                    "matches": [],
                    "skipped": True,
                    "reason": "unsupported_language_for_languagetool",
                    "language": language,
                },
            )

        try:
            tool = self._tool_factory(language)
            all_matches = tool.check(sentence)
        except Exception as exc:  # pragma: no cover - environment-dependent
            details = build_languagetool_details(
                sentence=sentence,
                all_matches=[],
                grammar_matches=[],
                error=str(exc),
            )
            return EvaluationResult(score=0.0, details=details)

        grammar_matches = filter_grammar_matches(all_matches)
        details = build_languagetool_details(
            sentence=sentence,
            all_matches=all_matches,
            grammar_matches=grammar_matches,
        )
        return EvaluationResult(
            score=1.0 if details["passed"] else 0.0,
            details=details,
        )
