"""Clausal complexity via spaCy dependency labels."""

from __future__ import annotations

from typing import Any

from research.evaluation.morph_configs import load_morph_config
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.verb_morphology import _get_spacy_nlp

EVALUATOR_NAME = "clause_count"

_SUBORDINATE_DEPS = frozenset({"ccomp", "xcomp", "advcl", "relcl"})
_MAX_CLAUSES_FOR_SCORE = 4


def count_clauses(doc) -> int:
    """Count clausal predicates: main (ROOT) + subordinate + coordinated verbs."""
    has_root_verb = False
    extra_clauses: set[int] = set()

    for token in doc:
        if token.pos_ not in ("VERB", "AUX"):
            continue
        if token.dep_ == "ROOT":
            has_root_verb = True
        elif token.dep_ in _SUBORDINATE_DEPS:
            extra_clauses.add(token.i)
        elif token.dep_ == "conj" and token.head.pos_ in ("VERB", "AUX"):
            extra_clauses.add(token.i)

    if not has_root_verb and not extra_clauses:
        return 0
    base = 1 if has_root_verb else 0
    return base + len(extra_clauses)


def normalised_clause_score(clause_count: int) -> float:
    """Map raw clause count to [0, 1] for roll-ups."""
    if clause_count <= 0:
        return 0.0
    return round(min(clause_count, _MAX_CLAUSES_FOR_SCORE) / _MAX_CLAUSES_FOR_SCORE, 4)


class ClauseCountEvaluator(BaseEvaluator):
    """spaCy-based clausal count; score is normalised complexity in [0, 1]."""

    @property
    def name(self) -> str:
        return "clause_count"

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        language = (constraints.get("target_language") or "es").strip()
        try:
            config = load_morph_config(language)
            nlp = _get_spacy_nlp(config["model"])
            doc = nlp(sentence)
        except Exception as exc:
            return EvaluationResult(
                score=0.0,
                details={
                    "parse_ok": False,
                    "clause_count": None,
                    "error": str(exc),
                    "tool": "spacy",
                },
            )

        clauses = count_clauses(doc)
        return EvaluationResult(
            score=normalised_clause_score(clauses),
            details={
                "parse_ok": True,
                "clause_count": clauses,
                "tool": "spacy",
                "model": config["model"],
            },
        )
