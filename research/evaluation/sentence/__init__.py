"""Per-sentence evaluators: one ``BaseEvaluator`` subclass per module is typical."""

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.clause_count import ClauseCountEvaluator
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.length_in_band import LengthInBandEvaluator
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.evaluation.sentence.verb_morphology import VerbMorphologyEvaluator

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

__all__ = [
    "BaseEvaluator",
    "ClauseCountEvaluator",
    "EvaluationResult",
    "ExpectedFormMatchEvaluator",
    "LanguageToolGrammarEvaluator",
    "LengthInBandEvaluator",
    "VerbMorphologyEvaluator",
    "DEFAULT_EVALUATORS",
]
