"""Per-sentence evaluators: one ``BaseEvaluator`` subclass per module is typical."""

from typing import Callable

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.clause_count import ClauseCountEvaluator
from research.evaluation.sentence.cysill import CysillGrammarEvaluator
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.fluency_perplexity import FluencyPerplexityEvaluator
from research.evaluation.sentence.length_in_band import LengthInBandEvaluator
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.evaluation.sentence.naturalness_llm_judge import (
    NaturalnessLlmJudgeEvaluator,
)
from research.evaluation.sentence.verb_morphology import VerbMorphologyEvaluator

# LanguageTool has no Welsh grammar pack. For ``cy``, omit LT; Cysill is opt-in
# only via ``--with-cysill`` (see OPTIONAL_EVALUATORS).
_LANGUAGES_WITHOUT_LANGUAGETOOL: frozenset[str] = frozenset({"cy"})

# NOTE: VerbMorphologyEvaluator is intentionally *not* in DEFAULT_EVALUATORS.
# It depends on spaCy's `es_core_news_sm`, which mis-tags common Spanish verb
# forms (e.g. `busqué` labelled Mood=Sub/Pres/3sg instead of Ind/Pret/1sg).
# The evaluator was silently returning 0.0 across all runs due to a missing
# model on the cluster, and even when installed its output is unreliable
# enough that we prefer to compute agreement metrics offline / by rule.
# Import kept for callers that opt in explicitly (e.g. Direction 2 rescoring).
DEFAULT_EVALUATORS: list[BaseEvaluator] = [
    ExpectedFormMatchEvaluator(),
    LanguageToolGrammarEvaluator(),
    LengthInBandEvaluator(),
    ClauseCountEvaluator(),
]

# Opt-in evaluators. Cluster generation scripts never enable these by default
# (expensive / rate-limited / credits). Wire them in via CLI flags or offline
# rescore.
OPTIONAL_EVALUATORS: dict[str, Callable[[], BaseEvaluator]] = {
    FluencyPerplexityEvaluator().name: FluencyPerplexityEvaluator,
    NaturalnessLlmJudgeEvaluator().name: NaturalnessLlmJudgeEvaluator,
    CysillGrammarEvaluator().name: CysillGrammarEvaluator,
}


def default_evaluators_for_language(language: str) -> list[BaseEvaluator]:
    """Default per-sentence evaluators for a benchmark language code."""
    code = (language or "").strip().lower()
    if code in _LANGUAGES_WITHOUT_LANGUAGETOOL:
        return [ev for ev in DEFAULT_EVALUATORS if ev.name != "grammar_languagetool"]
    return list(DEFAULT_EVALUATORS)


def build_optional_evaluators(names: list[str]) -> list[BaseEvaluator]:
    """Instantiate optional evaluators by name; raise on unknown names."""
    out: list[BaseEvaluator] = []
    for n in names:
        factory = OPTIONAL_EVALUATORS.get(n)
        if factory is None:
            raise ValueError(
                f"Unknown optional evaluator '{n}'. "
                f"Known: {sorted(OPTIONAL_EVALUATORS)}"
            )
        out.append(factory())
    return out


__all__ = [
    "BaseEvaluator",
    "ClauseCountEvaluator",
    "CysillGrammarEvaluator",
    "EvaluationResult",
    "ExpectedFormMatchEvaluator",
    "FluencyPerplexityEvaluator",
    "LanguageToolGrammarEvaluator",
    "LengthInBandEvaluator",
    "NaturalnessLlmJudgeEvaluator",
    "VerbMorphologyEvaluator",
    "DEFAULT_EVALUATORS",
    "OPTIONAL_EVALUATORS",
    "build_optional_evaluators",
    "default_evaluators_for_language",
]
