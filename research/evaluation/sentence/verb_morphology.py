"""Binary check: does the sentence contain the target verb in the requested morphology?

Parses the sentence with a per-language parser (currently spaCy), finds tokens whose
lemma matches the keyword or whose surface form matches ``expected_form``, and checks
UD ``Tense``/``Person``/``Number`` features against the constraint set. Strict:
``preterite`` means exactly ``Tense=Past`` (not ``Imp``); missing morphology counts
as failure.

Language knowledge lives in ``research/evaluation/morph_configs/<lang>.yaml`` — the
evaluator itself is language-agnostic.
"""

from __future__ import annotations

from typing import Any

from research.evaluation.morph_configs import load_morph_config
from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.expected_form import normalize_token, tokenize

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


def _observed(token) -> dict[str, str | None]:
    """Parser facts we store for the selected candidate token."""
    return {
        "Token": token.text,
        "Lemma": token.lemma_,
        "POS": token.pos_,
        "Tense": _first_morph(token, "Tense"),
        "Person": _first_morph(token, "Person"),
        "Number": _first_morph(token, "Number"),
    }


def _token_matches_expected_form(token, expected_form_norm: str | None) -> bool:
    if not expected_form_norm:
        return False
    return normalize_token(token.text) == expected_form_norm


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
        expected_form = (constraints.get("expected_form") or "").strip()

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
        expected_form_norm = normalize_token(expected_form) if expected_form else None
        raw_tokens = tokenize(sentence)
        expected_form_present = (
            expected_form_norm is not None
            and any(normalize_token(t) == expected_form_norm for t in raw_tokens)
        )

        lemma_tokens = [t for t in doc if t.lemma_.casefold() == keyword_norm]
        candidates_by_index: dict[int, tuple[Any, set[str]]] = {}
        for token in doc:
            sources: set[str] = set()
            if token.lemma_.casefold() == keyword_norm and token.pos_ in pos_filter:
                sources.add("lemma")
            if _token_matches_expected_form(token, expected_form_norm):
                sources.add("expected_form")
            if sources:
                candidates_by_index[token.i] = (token, sources)
        candidates = list(candidates_by_index.values())

        if not candidates:
            reason = "parser_disagreement" if expected_form_present else "lemma_not_found"
            return EvaluationResult(
                score=0.0,
                details={
                    "passed": False,
                    "language": language,
                    "keyword": keyword,
                    "expected_form": expected_form or None,
                    "expected_form_present": expected_form_present,
                    "parser_disagreement": expected_form_present,
                    "lemma_present": bool(lemma_tokens),
                    "candidates_checked": 0,
                    "matched_token": None,
                    "expected": expected,
                    "observed": None,
                    "tense_match": False,
                    "person_match": False,
                    "number_match": False,
                    "parse_ok": True,
                    "reason": reason,
                },
            )

        best_observed: dict[str, str | None] = {}
        best_token, best_sources = candidates[0]
        for token, sources in candidates:
            observed = _observed(token)
            tense_ok = observed["Tense"] == expected["Tense"]
            person_ok = observed["Person"] == expected["Person"]
            number_ok = observed["Number"] == expected["Number"]
            lemma_ok = token.lemma_.casefold() == keyword_norm
            pos_ok = token.pos_ in pos_filter
            if lemma_ok and pos_ok and tense_ok and person_ok and number_ok:
                return EvaluationResult(
                    score=1.0,
                    details={
                        "passed": True,
                        "language": language,
                        "keyword": keyword,
                        "expected_form": expected_form or None,
                        "expected_form_present": expected_form_present,
                        "parser_disagreement": False,
                        "lemma_present": True,
                        "candidates_checked": len(candidates),
                        "matched_token": token.text,
                        "candidate_source": sorted(sources),
                        "expected": expected,
                        "observed": observed,
                        "lemma_match": lemma_ok,
                        "pos_match": pos_ok,
                        "tense_match": True,
                        "person_match": True,
                        "number_match": True,
                        "parse_ok": True,
                    },
                )
            # Prefer expected-form candidates for diagnostics: they show where the
            # generated gold form is present but the parser analysis disagrees.
            if "expected_form" in sources or "expected_form" not in best_sources:
                best_observed = observed
                best_token = token
                best_sources = sources

        if not best_observed:
            best_observed = _observed(best_token)

        lemma_ok = best_token.lemma_.casefold() == keyword_norm
        pos_ok = best_token.pos_ in pos_filter
        parser_disagreement = expected_form_present and (
            not lemma_ok
            or not pos_ok
            or best_observed.get("Tense") != expected["Tense"]
            or best_observed.get("Person") != expected["Person"]
            or best_observed.get("Number") != expected["Number"]
        )
        if parser_disagreement and "lemma" not in best_sources:
            reason = "parser_disagreement"
        else:
            reason = "morph_mismatch"

        return EvaluationResult(
            score=0.0,
            details={
                "passed": False,
                "language": language,
                "keyword": keyword,
                "expected_form": expected_form or None,
                "expected_form_present": expected_form_present,
                "parser_disagreement": parser_disagreement,
                "lemma_present": bool(lemma_tokens),
                "candidates_checked": len(candidates),
                "matched_token": best_token.text,
                "candidate_source": sorted(best_sources),
                "expected": expected,
                "observed": best_observed,
                "lemma_match": lemma_ok,
                "pos_match": pos_ok,
                "tense_match": best_observed.get("Tense") == expected["Tense"],
                "person_match": best_observed.get("Person") == expected["Person"],
                "number_match": best_observed.get("Number") == expected["Number"],
                "parse_ok": True,
                "reason": reason,
            },
        )
