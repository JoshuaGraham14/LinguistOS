"""Binary check: does the sentence contain the target verb in the requested morphology?

Parses the sentence with a per-language parser (currently spaCy), finds tokens whose
lemma matches the keyword, and checks UD ``Tense``/``Person``/``Number`` features
against the constraint set. Strict: ``preterite`` means exactly ``Tense=Past`` (not
``Imp``); missing morphology counts as failure.

Language knowledge lives in ``research/evaluation/morph_configs/<lang>.yaml`` — the
evaluator itself is language-agnostic.
"""

from __future__ import annotations

from typing import Any

from research.evaluation.morph_configs import load_morph_config
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult

# Per-process cache of loaded spaCy models keyed on model name.
_NLP_CACHE: dict[str, Any] = {}


def _get_spacy_nlp(model_name: str):
    """Lazy-load and cache a spaCy model. Imports spaCy on first use."""
    if model_name in _NLP_CACHE:
        return _NLP_CACHE[model_name]
    import spacy

    nlp = spacy.load(model_name)
    _NLP_CACHE[model_name] = nlp
    return nlp


def _fail(reason: str, **details: Any) -> EvaluationResult:
    payload: dict[str, Any] = {"passed": False, "reason": reason}
    payload.update(details)
    return EvaluationResult(score=0.0, details=payload)


def _first_morph(token, feature: str) -> str | None:
    """First UD feature value on *token* (e.g. ``Tense`` → ``Past``)."""
    values = token.morph.get(feature)
    return values[0] if values else None


class VerbMorphologyEvaluator(BaseEvaluator):
    """Pass (1.0) when a token matches keyword lemma AND requested morphology."""

    @property
    def name(self) -> str:
        return "verb_morphology"

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        keyword = (constraints.get("keyword") or "").strip()
        language = (constraints.get("target_language") or "").strip()
        tense_in = constraints.get("tense")
        person_in = constraints.get("person")
        number_in = constraints.get("number")

        if not keyword:
            return _fail("missing_keyword")

        try:
            config = load_morph_config(language)
        except ValueError:
            return _fail("unsupported_language", language=language)

        expected: dict[str, str] = {}
        for ud_key, raw, map_name in (
            ("Tense", tense_in, "tense_map"),
            ("Person", person_in, "person_map"),
            ("Number", number_in, "number_map"),
        ):
            mapping = config[map_name]
            if raw not in mapping:
                return _fail(
                    "unsupported_tense" if ud_key == "Tense" else f"unsupported_{ud_key.lower()}",
                    language=language,
                    expected_key=ud_key,
                    received=raw,
                )
            expected[ud_key] = mapping[raw]

        pos_filter = set(config["pos_filter"])

        try:
            nlp = _get_spacy_nlp(config["model"])
        except Exception as exc:  # pragma: no cover - environment-dependent
            return _fail("parse_failed", error=str(exc))

        try:
            doc = nlp(sentence)
        except Exception as exc:  # pragma: no cover - parser-dependent
            return _fail("parse_failed", error=str(exc))

        keyword_norm = keyword.casefold()
        candidates = [
            t for t in doc
            if t.lemma_.casefold() == keyword_norm and t.pos_ in pos_filter
        ]

        if not candidates:
            return EvaluationResult(
                score=0.0,
                details={
                    "passed": False,
                    "language": language,
                    "keyword": keyword,
                    "lemma_present": False,
                    "candidates_checked": 0,
                    "matched_token": None,
                    "expected": expected,
                    "observed": None,
                    "tense_match": False,
                    "person_match": False,
                    "number_match": False,
                    "parse_ok": True,
                    "reason": "lemma_not_found",
                },
            )

        best_observed: dict[str, str | None] = {}
        best_token = candidates[0]
        for token in candidates:
            observed = {
                "Tense": _first_morph(token, "Tense"),
                "Person": _first_morph(token, "Person"),
                "Number": _first_morph(token, "Number"),
            }
            tense_ok = observed["Tense"] == expected["Tense"]
            person_ok = observed["Person"] == expected["Person"]
            number_ok = observed["Number"] == expected["Number"]
            if tense_ok and person_ok and number_ok:
                return EvaluationResult(
                    score=1.0,
                    details={
                        "passed": True,
                        "language": language,
                        "keyword": keyword,
                        "lemma_present": True,
                        "candidates_checked": len(candidates),
                        "matched_token": token.text,
                        "expected": expected,
                        "observed": observed,
                        "tense_match": True,
                        "person_match": True,
                        "number_match": True,
                        "parse_ok": True,
                    },
                )
            best_observed = observed
            best_token = token

        return EvaluationResult(
            score=0.0,
            details={
                "passed": False,
                "language": language,
                "keyword": keyword,
                "lemma_present": True,
                "candidates_checked": len(candidates),
                "matched_token": best_token.text,
                "expected": expected,
                "observed": best_observed,
                "tense_match": best_observed.get("Tense") == expected["Tense"],
                "person_match": best_observed.get("Person") == expected["Person"],
                "number_match": best_observed.get("Number") == expected["Number"],
                "parse_ok": True,
                "reason": "morph_mismatch",
            },
        )
