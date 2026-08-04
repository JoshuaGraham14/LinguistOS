"""Binary check: does the sentence contain the benchmark gold surface form?

Compares ``constraints["expected_form"]`` against whole tokens in the target
sentence (case-insensitive, punctuation-tolerant).

Spanish matching remains **accent-sensitive**. Welsh matching additionally:

- folds circumflex / diaeresis vowels (``ô``≈``o``, ``ï``≈``i``, …)
- expands colloquial / soft-mutated **auxiliaries** (shared across verbs)
- expands finite **``-oi`` verb** orthographic variants (class-general)

Optional multi-piece extensions (backward compatible):

- ``expected_form_alts``: ``|``-separated alternatives; any one match counts
  for the primary form.
- ``expected_aux`` / ``expected_aux_alts``: companion auxiliary that must also
  appear (periphrastic constructions).
- ``particle``: optional particle token that must also appear (e.g. Welsh *yn*).
  For Welsh ``yn``, also accepts clitic ``'n`` / ``’n`` (e.g. ``i'n``).
- Context-aware **mutation** expansion for Welsh lexical forms (see
  ``research.welsh.mutation``): e.g. periphrastic past accepts soft-mutated
  verbnoun surfaces derived from the radical, without treating every
  mutation as freely valid in every cell.
"""

from __future__ import annotations

import string
from typing import Any

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.welsh.ef_surfaces import (
    expand_aux_surfaces,
    expand_oi_form_variants,
    fold_welsh_accents,
)
from research.welsh.mutation import (
    expand_mutation_candidates,
    mutation_policy_for_constraints,
)

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
    """Case-fold a token for comparison; accents are preserved (Spanish-safe)."""
    return token.casefold()


def normalize_token_welsh(token: str) -> str:
    """Case-fold + fold Welsh vowel diacritics for comparison."""
    return fold_welsh_accents(token)


def _split_alts(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [p.strip() for p in text.split("|") if p.strip()]


def _is_welsh_context(constraints: dict[str, Any]) -> bool:
    lang = str(constraints.get("target_language") or "").strip().casefold()
    if lang in {"cy", "welsh", "cymraeg"}:
        return True
    # Welsh peri cells sometimes omit target_language in unit tests.
    return str(constraints.get("construction") or "").strip().casefold() == "periphrastic"


def _match_any(
    tokens: list[str],
    candidates: list[str],
    *,
    welsh: bool = False,
) -> str | None:
    if not candidates:
        return None
    norm = normalize_token_welsh if welsh else normalize_token
    wanted = {norm(c) for c in candidates}
    for token in tokens:
        forms = [norm(token)]
        # Welsh clitics attach with apostrophe: gredu'r, i'n, o'n.
        for sep in ("'", "’"):
            if sep in token:
                forms.append(norm(token.split(sep, 1)[0]))
                break
        for form in forms:
            if form in wanted:
                return token
    return None


def _particle_candidates(particle: str, *, welsh: bool) -> list[str]:
    cands = [particle]
    if welsh and particle.casefold() == "yn":
        cands.extend(["'n", "’n"])
    return cands


def _match_particle(tokens: list[str], particle: str, *, welsh: bool) -> str | None:
    """Match ``yn`` as a free token or as a clitic ``…'n`` (Welsh)."""
    direct = _match_any(
        tokens, _particle_candidates(particle, welsh=welsh), welsh=welsh
    )
    if direct is not None:
        return direct
    if not (welsh and particle.casefold() == "yn"):
        return None
    norm = normalize_token_welsh if welsh else normalize_token
    for token in tokens:
        low = norm(token)
        if low.endswith("'n") or low.endswith("’n"):
            return token
    return None


def _lemma_from_constraints(constraints: dict[str, Any]) -> str:
    for key in ("keyword", "lemma", "verb"):
        val = constraints.get(key)
        if val:
            return str(val).strip()
    return ""


def _lexical_form_candidates(
    constraints: dict[str, Any], expected: str, *, welsh: bool
) -> tuple[list[str], str]:
    """Listed gold/alts plus mutation / -oi class surfaces."""
    listed = [expected, *_split_alts(constraints.get("expected_form_alts"))]
    lemma = _lemma_from_constraints(constraints)
    expanded: list[str] = []
    seen: set[str] = set()

    def _add_all(forms: list[str]) -> None:
        for f in forms:
            if not f:
                continue
            key = normalize_token_welsh(f) if welsh else normalize_token(f)
            if key in seen:
                continue
            seen.add(key)
            expanded.append(f)

    _add_all(listed)
    if welsh:
        for f in list(expanded):
            _add_all(expand_oi_form_variants(f, lemma=lemma))

    policy = mutation_policy_for_constraints(constraints)
    if policy == "none":
        return expanded, policy
    return expand_mutation_candidates(expanded, policy=policy), policy


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
        welsh = _is_welsh_context(constraints)
        primary_candidates, mutation_policy = _lexical_form_candidates(
            constraints, expected, welsh=welsh
        )
        matched = _match_any(tokens, primary_candidates, welsh=welsh)
        norm = normalize_token_welsh if welsh else normalize_token
        listed = {
            norm(c)
            for c in [expected, *_split_alts(constraints.get("expected_form_alts"))]
        }
        matched_via_mutation = matched is not None and norm(matched) not in listed

        matched_aux: str | None = None
        aux = (constraints.get("expected_aux") or "").strip()
        aux_ok = True
        aux_candidates: list[str] = []
        if aux:
            raw_alts = _split_alts(constraints.get("expected_aux_alts"))
            if welsh:
                aux_candidates = expand_aux_surfaces(aux, raw_alts)
            else:
                aux_candidates = [aux, *raw_alts]
            matched_aux = _match_any(tokens, aux_candidates, welsh=welsh)
            aux_ok = matched_aux is not None

        matched_particle: str | None = None
        particle = (constraints.get("particle") or "").strip()
        particle_ok = True
        if particle:
            matched_particle = _match_particle(tokens, particle, welsh=welsh)
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
                "mutation_policy": mutation_policy,
                "form_candidates": primary_candidates,
                "aux_candidates": aux_candidates or None,
                "matched_via_mutation": matched_via_mutation,
                **({"reason": reason} if reason else {}),
            },
        )
