"""Input-dependent Spanish morphology bans for Direction 3 decoding.

The benchmark's ``expected_form`` remains the source of truth.  Verbecc is
used only to derive competing forms; a dictionary disagreement can therefore
never cause the requested surface form itself to be banned.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from research.evaluation.lexicon.frequency import _actual_es_form

MorphBanMode = Literal["full", "forms_only", "pronouns_only"]

INDICATIVE_TENSES: tuple[str, ...] = (
    "present",
    "preterite",
    "imperfect",
    "future",
    "conditional",
)
PERSON_NUMBER_SLOTS: tuple[tuple[str, str], ...] = (
    ("1st", "singular"),
    ("2nd", "singular"),
    ("3rd", "singular"),
    ("1st", "plural"),
    ("2nd", "plural"),
    ("3rd", "plural"),
)

# Include polite Spanish subject pronouns in the same agreement group.  Do not
# include unaccented "el": globally banning it would also ban the article.
_SUBJECT_GROUPS: dict[tuple[str, str], frozenset[str]] = {
    ("1st", "singular"): frozenset({"yo"}),
    ("2nd", "singular"): frozenset({"tú", "tu"}),
    ("3rd", "singular"): frozenset({"él", "ella", "usted"}),
    ("1st", "plural"): frozenset({"nosotros", "nosotras"}),
    ("2nd", "plural"): frozenset({"vosotros", "vosotras"}),
    ("3rd", "plural"): frozenset({"ellos", "ellas", "ustedes"}),
}
_ALL_SUBJECT_PRONOUNS = frozenset().union(*_SUBJECT_GROUPS.values())
_WORD_RE = re.compile(r"[^\W\d_]+", flags=re.UNICODE)


def normalize_surface(value: str) -> str:
    """NFC-normalise and case-fold a surface form."""
    return unicodedata.normalize("NFC", value).strip().casefold()


@dataclass(frozen=True)
class MorphBanSet:
    """Surface strings prohibited for one benchmark cell."""

    mode: MorphBanMode
    competing_forms: frozenset[str]
    pronouns: frozenset[str]

    @property
    def surfaces(self) -> frozenset[str]:
        return self.competing_forms | self.pronouns


@lru_cache(maxsize=4096)
def _paradigm_forms(lemma: str, tense: str) -> tuple[str, ...]:
    forms: set[str] = set()
    for person, number in PERSON_NUMBER_SLOTS:
        form = _actual_es_form(lemma, tense, person, number)
        if form:
            forms.add(normalize_surface(form))
    return tuple(sorted(forms))


def _wrong_pronouns(person: str, number: str) -> frozenset[str]:
    allowed = _SUBJECT_GROUPS.get((person, number))
    if allowed is None:
        return frozenset()
    return frozenset(_ALL_SUBJECT_PRONOUNS - allowed)


def build_morph_ban_set(
    lemma: str,
    tense: str,
    person: str,
    number: str,
    expected_form: str,
    *,
    mode: MorphBanMode = "full",
) -> MorphBanSet:
    """Build form/pronoun bans for a single Spanish morphology cell."""
    if mode not in ("full", "forms_only", "pronouns_only"):
        raise ValueError(f"Unknown morphology ban mode: {mode!r}")

    lemma_norm = normalize_surface(lemma)
    expected_norm = normalize_surface(expected_form)
    form_bans: set[str] = set()

    if mode in ("full", "forms_only"):
        if tense == "participle":
            for indicative_tense in INDICATIVE_TENSES:
                form_bans.update(_paradigm_forms(lemma_norm, indicative_tense))
        elif tense in INDICATIVE_TENSES:
            form_bans.update(_paradigm_forms(lemma_norm, tense))
            actual = _actual_es_form(lemma_norm, tense, person, number)
            if actual and normalize_surface(actual) != expected_norm:
                warnings.warn(
                    "Benchmark/verbecc disagreement for "
                    f"{lemma_norm} {tense} {person} {number}: "
                    f"benchmark={expected_form!r}, verbecc={actual!r}; "
                    "trusting benchmark expected_form",
                    RuntimeWarning,
                    stacklevel=2,
                )
        form_bans.add(lemma_norm)
        # The benchmark gold is an unconditional allow-list singleton.
        form_bans.discard(expected_norm)

    pronoun_bans = (
        _wrong_pronouns(person, number)
        if mode in ("full", "pronouns_only") and tense != "participle"
        else frozenset()
    )
    return MorphBanSet(
        mode=mode,
        competing_forms=frozenset(form_bans),
        pronouns=pronoun_bans,
    )


def _case_variants(surface: str) -> tuple[str, ...]:
    variants = [surface]
    capitalized = surface[:1].upper() + surface[1:]
    if capitalized not in variants:
        variants.append(capitalized)
    return tuple(variants)


def encode_bad_words(tokenizer, ban_set: MorphBanSet) -> list[list[int]]:
    """Encode bare/space-prefixed and sentence-initial variants."""
    encoded: list[list[int]] = []
    for surface in sorted(ban_set.surfaces):
        for case_variant in _case_variants(surface):
            for prefix in ("", " "):
                token_ids = tokenizer.encode(
                    prefix + case_variant,
                    add_special_tokens=False,
                )
                if token_ids and token_ids not in encoded:
                    encoded.append(token_ids)
    return encoded


def banned_surfaces_in_text(text: str, ban_set: MorphBanSet) -> frozenset[str]:
    """Return banned whole-word surfaces observed in decoded text."""
    tokens = {normalize_surface(token) for token in _WORD_RE.findall(text)}
    return frozenset(surface for surface in ban_set.surfaces if surface in tokens)
