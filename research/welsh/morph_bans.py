"""Welsh thin morphology bans for Neurologic decode (Eurfa-backed).

Spanish bans live in ``research.generation.morph_bans`` (verbecc). This module
is Welsh-only: competing surfaces come from Eurfa, pronouns are Welsh, and the
returned object is the shared ``MorphBanSet`` so Neurologic encoding stays
unchanged.

Thin mode (mirror Spanish thin):

* synthetic: wrong subject pronouns + 1sg/3sg competing finite forms
* periphrastic: wrong pronouns + 1sg/3sg competing aux forms + same-tense
  synthetic finite forms of the lemma (anti construction-flip)

Gold ``expected_form`` / ``expected_aux`` (and alts) are never banned.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

import pandas as pd

from research.generation.morph_bans import MorphBanSet, normalize_surface
from research.welsh.mutation import soft_mutate
from research.welsh.scripts.build_welsh_cases import (
    PERSON_TO_PN,
    _index_eurfa,
    _person_frame,
    _surfaces_for,
)
from research.welsh.scripts.select_welsh_verbs import DEFAULT_EURFA, _load_eurfa

WelshMorphBanMode = Literal["thin"]

# Benchmark (person, number) ↔ Eurfa person code.
_PN_TO_EURFA: dict[tuple[str, str], str] = {
    (person, number): code for code, (person, number) in PERSON_TO_PN.items()
}

# Thin competitors: habitual 1sg / 3sg fallbacks (same slots as Spanish thin).
_THIN_COMPETITOR_SLOTS: tuple[tuple[str, str], ...] = (
    ("1st", "singular"),
    ("3rd", "singular"),
)

_SUBJECT_GROUPS: dict[tuple[str, str], frozenset[str]] = {
    ("1st", "singular"): frozenset({"fi", "i", "mi"}),
    ("2nd", "singular"): frozenset({"ti", "di"}),
    ("3rd", "singular"): frozenset({"e", "o", "hi", "fe", "fo"}),
    ("1st", "plural"): frozenset({"ni"}),
    ("2nd", "plural"): frozenset({"chi"}),
    ("3rd", "plural"): frozenset({"nhw", "hwy"}),
}
_ALL_SUBJECT_PRONOUNS = frozenset().union(*_SUBJECT_GROUPS.values())

# Grid tense → Eurfa lexical tense for synthetic competitors.
_LEXICAL_EURFA_TENSE: dict[str, str] = {
    "present": "pres",
    "past": "past",
    "imperfect": "imperf",
}

# Periphrastic tense → (aux lemma, Eurfa aux tense).
_PERI_AUX: dict[str, tuple[str, str]] = {
    "present": ("bod", "pres"),
    "past": ("gwneud", "past"),
    "imperfect": ("bod", "imperf"),
    "future": ("bod", "fut"),
}


def _wrong_pronouns(person: str, number: str) -> frozenset[str]:
    allowed = _SUBJECT_GROUPS.get((person, number))
    if allowed is None:
        return frozenset()
    return frozenset(_ALL_SUBJECT_PRONOUNS - allowed)


def _allowlist_from_constraints(constraints: dict[str, Any]) -> set[str]:
    """Surfaces that must never appear in the ban set."""
    allowed: set[str] = set()
    for key in ("expected_form", "expected_aux"):
        raw = constraints.get(key)
        if raw:
            allowed.add(normalize_surface(str(raw)))
    for key in ("expected_form_alts", "expected_aux_alts", "match_forms"):
        raw = constraints.get(key)
        if not raw:
            continue
        for part in str(raw).split("|"):
            part = part.strip()
            if part:
                allowed.add(normalize_surface(part))
    # Soft-mutated VN (peri past) and radical VN companions.
    form = str(constraints.get("expected_form") or "").strip()
    if form:
        allowed.add(normalize_surface(soft_mutate(form)))
    return allowed


@lru_cache(maxsize=1)
def _eurfa_index() -> dict[str, dict[str, pd.DataFrame]]:
    return _index_eurfa(_load_eurfa(DEFAULT_EURFA))


def _eurfa_surfaces(lemma: str, eurfa_tense: str, person_code: str) -> list[str]:
    tense_map = _eurfa_index().get(lemma, {})
    frame = tense_map.get(eurfa_tense, pd.DataFrame())
    if frame.empty:
        return []
    return _surfaces_for(_person_frame(frame, person_code))


def _thin_slot_forms(
    lemma: str,
    eurfa_tense: str,
    person: str,
    number: str,
    *,
    allowlist: set[str],
) -> set[str]:
    """1sg/3sg competitors for *lemma*@*eurfa_tense*, excluding allowlist."""
    forms: set[str] = set()
    for slot_person, slot_number in _THIN_COMPETITOR_SLOTS:
        if (slot_person, slot_number) == (person, number):
            continue
        code = _PN_TO_EURFA.get((slot_person, slot_number))
        if not code:
            continue
        for surf in _eurfa_surfaces(lemma, eurfa_tense, code):
            norm = normalize_surface(surf)
            if norm and norm not in allowlist:
                forms.add(norm)
    return forms


def build_welsh_morph_ban_set(
    lemma: str,
    constraints: dict[str, Any],
    *,
    mode: WelshMorphBanMode = "thin",
) -> MorphBanSet:
    """Build thin Welsh form/pronoun bans for one morphology cell."""
    if mode != "thin":
        raise ValueError(f"Unsupported Welsh morph ban mode: {mode!r}")

    construction = str(constraints.get("construction") or "").strip().casefold()
    tense = str(constraints.get("tense") or "").strip()
    person = str(constraints.get("person") or "").strip()
    number = str(constraints.get("number") or "").strip()
    allowlist = _allowlist_from_constraints(constraints)

    form_bans: set[str] = set()

    if construction == "synthetic":
        eurfa_tense = _LEXICAL_EURFA_TENSE.get(tense)
        if eurfa_tense:
            form_bans.update(
                _thin_slot_forms(
                    lemma,
                    eurfa_tense,
                    person,
                    number,
                    allowlist=allowlist,
                )
            )
    elif construction == "periphrastic":
        aux_spec = _PERI_AUX.get(tense)
        if aux_spec:
            aux_lemma, aux_tense = aux_spec
            form_bans.update(
                _thin_slot_forms(
                    aux_lemma,
                    aux_tense,
                    person,
                    number,
                    allowlist=allowlist,
                )
            )
        # Anti construction-flip: ban thin synthetic competitors when Eurfa has them.
        lex_tense = _LEXICAL_EURFA_TENSE.get(tense)
        if lex_tense:
            form_bans.update(
                _thin_slot_forms(
                    lemma,
                    lex_tense,
                    person,
                    number,
                    allowlist=allowlist,
                )
            )

    # Never ban gold / allowlisted surfaces (belt and braces).
    form_bans -= allowlist

    pronoun_bans = (
        _wrong_pronouns(person, number) if person and number else frozenset()
    )

    return MorphBanSet(
        mode="thin",
        competing_forms=frozenset(form_bans),
        pronouns=frozenset(normalize_surface(p) for p in pronoun_bans),
        allowed_subjects=frozenset(),
        gate_forms_on_subject=False,
    )


def welsh_neurologic_positive_form(constraints: dict[str, Any]) -> str:
    """Positive Neurologic literal: aux for peri, expected_form otherwise."""
    construction = str(constraints.get("construction") or "").strip().casefold()
    if construction == "periphrastic":
        aux = str(constraints.get("expected_aux") or "").strip()
        if aux:
            return aux
    return str(constraints.get("expected_form") or "").strip()
