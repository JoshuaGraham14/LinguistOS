"""English past-tense irregularity for Diagnostic 1 stratified sampling.

Classifies census verbs programmatically (lemminflect past vs naive ``-ed``),
mirroring Spanish ``verbecc``-based irregularity. Pure consonant-doubling /
``y→ied`` spelling variants count as regular.
"""

from __future__ import annotations

from functools import lru_cache

import lemminflect

from research.evaluation.lexicon.frequency import _en_regular_forms

# Legacy hand-curated set — kept for Zipf lemma-summed scoring in frequency.py,
# not used for sampling irregularity anymore.
from research.evaluation.lexicon.en_irregular import EN_IRREGULAR_FORMS

_EXTRA_IRREGULAR_LEMMAS: frozenset[str] = frozenset({
    "cleave", "forego", "forgo", "forswear", "gird", "betide", "wreak",
    "outdo", "slink", "unbind", "misunderstand", "cling", "stink", "weep",
    "stride", "withstand", "knit", "wed", "tread", "overthrow", "slay",
    "kneel", "shear", "withhold", "slit", "overtake", "sling", "mow",
    "fling", "heave", "strew", "gainsay", "beseech", "shrive", "forswear",
})

EN_IRREGULAR_LEMMAS: frozenset[str] = (
    frozenset(EN_IRREGULAR_FORMS.keys()) | _EXTRA_IRREGULAR_LEMMAS
)


def _naive_ed_past(lemma: str) -> str:
    return _en_regular_forms(lemma.lower())[2].lower()


def _normalize_lem_form(form: str) -> str:
    """Collapse lemminflect spacing/hyphen variants to a single token."""
    return form.lower().replace("-", "").replace(" ", "")


@lru_cache(maxsize=16384)
def _lemminflect_past(lemma: str) -> str | None:
    stem = lemma.lower()
    forms = lemminflect.getInflection(stem, "VBD")
    if not forms:
        return None
    return _normalize_lem_form(forms[0])


def _is_doubling_only(lemma: str, past: str, naive: str) -> bool:
    """True when past differs from naive ``-ed`` only by orthographic doubling."""
    stem = lemma.lower()
    if len(stem) >= 2 and past == stem + stem[-1] + "ed" and naive == stem + "ed":
        return True
    if (
        stem.endswith("y")
        and len(stem) >= 2
        and stem[-2] not in "aeiou"
        and past == stem[:-1] + "ied"
        and naive == stem[:-1] + "ied"
    ):
        return True
    return False


@lru_cache(maxsize=16384)
def en_past_tense_irregular(lemma: str) -> bool:
    """True if *lemma*'s past tense is not the regular ``-ed`` form."""
    stem = lemma.lower()
    past = _lemminflect_past(stem)
    if past is None:
        return stem in EN_IRREGULAR_LEMMAS
    naive = _naive_ed_past(stem)
    if past == naive:
        return False
    if _is_doubling_only(stem, past, naive):
        return False
    return True
