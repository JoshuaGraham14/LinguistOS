"""Objective verb rarity: Zipf-scale lemma frequency and tense-specific irregularity.

Purpose
-------
Replace the LLM-generated 'common / mid / rare' labels currently baked into
`research/benchmarks/*.yaml` with an externally verifiable, per-language
frequency score, addressing supervisor feedback from 22 June 2026:

  * Rarity must be defined objectively (external corpus, not model intuition).
  * Cutoffs must be principled and pre-registered, not asserted post hoc.
  * Rarity must be disentangled from irregularity, since a 'rare verb'
    result can otherwise be an 'irregular verb' result in disguise.

Design decisions
----------------
1. **Frequency source**: `wordfreq`, a large aggregate corpus (Wikipedia +
   OpenSubtitles + news + web). Not publication-only; we surface this as
   a methods-section caveat rather than blocking on CORPES XXI / Google Books
   Ngram integration.

2. **Score axis**: Zipf (log10 of per-billion frequency). Standard in
   psycholinguistics; human-readable.

3. **Lemma frequency, not surface form**: raw `word_frequency` is computed
   over a canonical inflected-form set (infinitive, present indicative x6,
   gerund, past participle) and summed *before* Zipf-transform. Fixes a real
   issue for Spanish: the infinitive is often not the most-used form of the
   verb (e.g. 'habla' >> 'hablar').

4. **Tier cutoffs**: per-language 33rd/67th percentile of the Zipf-lemma
   distribution over a **full verb census** (~1,180 Spanish verbs from
   wordfreq top-30k, validated by verbecc). Values are computed once by
   `research/scripts/build_verb_census.py` and frozen in `TIER_CUTOFFS`.
   Tiers are named high / mid / low (not common/rare) to avoid implying
   absolute rarity for verbs inside the census. Freezing = pre-registration.

5. **Irregularity is tense-specific**: `is_irregular(verb, tense)` compares
   verbecc's actual conjugation against the regular-paradigm form derived
   from hand-coded Spanish endings. Reflects that Spanish irregularity
   attaches to (verb, tense), not to the verb as a whole
   (e.g. 'tener' is irregular in present indicative, regular in imperfect).

English handling is minimal: `verb_zipf` and `tier` work, but
`is_irregular` raises `NotImplementedError`.
"""

from __future__ import annotations

import csv
import logging
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Literal

from wordfreq import word_frequency

logging.getLogger("verbecc").setLevel(logging.WARNING)

Tier = Literal["high", "mid", "low"]

CENSUS_DIR = Path(__file__).resolve().parent / "census"

# Frozen 33rd / 67th percentile Zipf-lemma cutoffs per language.
#
# Provenance: `research/scripts/build_verb_census.py` over the full verb
# census in `research/evaluation/lexicon/census/{lang}.csv`.
#
# Tuple is (low_upper, high_lower):
#   Zipf < low_upper  -> low-frequency tier
#   Zipf >= high_lower -> high-frequency tier
#   otherwise -> mid
#
# Verbs outside the census (e.g. literary lemmas below wordfreq top-30k)
# are scored via verb_zipf() and compared against these same boundaries.
#
# Regenerate census + cutoffs: python -m research.scripts.build_verb_census
TIER_CUTOFFS: dict[str, tuple[float, float]] = {
    "es": (4.131, 4.693),  # n=1180, min=3.219, max=7.213, mean=4.456
    "en": (3.915, 4.656),  # n=2265, min=3.004, max=6.799, mean=4.287
}

# Canonical forms summed for lemma frequency. Kept small (~9 forms) to
# stay dominated by the most-used surface forms; adding low-frequency
# subjunctive forms mainly adds noise.
_ES_CANONICAL_TENSES: tuple[tuple[str, str], ...] = (
    ("indicativo", "presente"),
)
_ES_NON_PERSONAL: tuple[tuple[str, str], ...] = (
    ("infinitivo", "infinitivo"),
    ("gerundio", "gerundio"),
    ("participo", "participo"),
)

# Internal tense name -> (verbecc mood, verbecc tense).
_ES_TENSE_MAP: dict[str, tuple[str, str]] = {
    "present": ("indicativo", "presente"),
    "preterite": ("indicativo", "pretérito-perfecto-simple"),
    "imperfect": ("indicativo", "pretérito-imperfecto"),
    "future": ("indicativo", "futuro"),
    "conditional": ("condicional", "presente"),
}

# Person / number -> verbecc (p, n) tuple.
_ES_PN_KEYS = {
    ("1st", "singular"): ("1", "s"),
    ("2nd", "singular"): ("2", "s"),
    ("3rd", "singular"): ("3", "s"),
    ("1st", "plural"): ("1", "p"),
    ("2nd", "plural"): ("2", "p"),
    ("3rd", "plural"): ("3", "p"),
}


@lru_cache(maxsize=1)
def _conjugator():
    """Cached verbecc conjugator; imported lazily to keep the module light."""
    from verbecc import CompleteConjugator  # type: ignore[import-untyped]

    return CompleteConjugator(lang="es")


@lru_cache(maxsize=4096)
def _conjugate_es(verb: str) -> dict | None:
    try:
        return _conjugator().conjugate(verb).get_data()
    except Exception:
        return None


def _strip_pronoun(chunk: str) -> str:
    """verbecc entries look like 'yo hablo' or 'nosotros hablamos'; keep the verb."""
    parts = chunk.split()
    return parts[-1] if parts else chunk


def _es_canonical_forms(verb: str) -> list[str]:
    """Return the inflected forms used for lemma-summed Spanish frequency."""
    data = _conjugate_es(verb)
    if data is None:
        return [verb]

    forms: list[str] = []
    moods = data["moods"]

    for mood, tense in _ES_CANONICAL_TENSES:
        entries = moods.get(mood, {}).get(tense, [])
        # Deduplicate: verbecc emits multiple 3rd-person rows (él/ella/usted)
        # that share the same surface form; count each surface form once.
        seen: set[str] = set()
        for entry in entries:
            for chunk in entry.get("c", []):
                form = _strip_pronoun(chunk)
                if form not in seen:
                    seen.add(form)
                    forms.append(form)

    for mood, tense in _ES_NON_PERSONAL:
        entries = moods.get(mood, {}).get(tense, [])
        for entry in entries:
            for chunk in entry.get("c", []):
                form = _strip_pronoun(chunk)
                forms.append(form)

    if verb not in forms:
        forms.insert(0, verb)
    return forms


def _en_canonical_forms(verb: str) -> list[str]:
    """Minimal English form set: infinitive plus regular -s / -ed / -ing.

    English is peripheral to this project; we don't try to handle strong
    verbs. This is enough for the cross-lingual comparison to be sensible.
    """
    stem = verb
    forms = [verb]
    if stem.endswith("e"):
        forms += [f"{stem}s", f"{stem}d", f"{stem[:-1]}ing"]
    elif stem.endswith("y") and len(stem) >= 2 and stem[-2] not in "aeiou":
        forms += [f"{stem[:-1]}ies", f"{stem[:-1]}ied", f"{stem}ing"]
    else:
        forms += [f"{stem}s", f"{stem}ed", f"{stem}ing"]
    return forms


def _zipf(freq_per_word: float) -> float:
    """Convert a `word_frequency` value (per-word) to Zipf (log10 per billion)."""
    if freq_per_word <= 0.0:
        return 0.0
    return math.log10(freq_per_word * 1_000_000_000)


def verb_zipf(verb: str, lang: str) -> float:
    """Lemma-summed Zipf frequency for *verb* in *lang*.

    Sums raw `word_frequency` over a canonical inflected-form set, then
    Zipf-transforms the total. Falls back to the raw surface-form Zipf
    of the infinitive if the conjugator can't produce forms.
    """
    if lang == "es":
        forms = _es_canonical_forms(verb)
    elif lang == "en":
        forms = _en_canonical_forms(verb)
    else:
        return _zipf(word_frequency(verb, lang))

    total = sum(word_frequency(f, lang) for f in forms)
    if total <= 0.0:
        # Fall back to bare-infinitive lookup so unknown verbs still get a value.
        total = word_frequency(verb, lang)
    return _zipf(total)


def tier_from_zipf(z: float, lang: str) -> Tier:
    """Map a Zipf-lemma score to high / mid / low using frozen cutoffs."""
    low_upper, high_lower = TIER_CUTOFFS.get(lang, (0.0, 0.0))
    if z < low_upper:
        return "low"
    if z >= high_lower:
        return "high"
    return "mid"


def tier(verb: str, lang: str) -> Tier:
    """Return the frequency tier for *verb* in *lang*.

    Census verbs use the Zipf score committed in ``census/{lang}.csv`` so
    tier boundaries stay consistent with the pre-registered cutoffs. Verbs
    outside the census (e.g. niche literary lemmas) are scored live via
    ``verb_zipf()``.
    """
    for v, z in _load_census(lang):
        if v == verb:
            return tier_from_zipf(z, lang)
    return tier_from_zipf(verb_zipf(verb, lang), lang)


@lru_cache(maxsize=4)
def _load_census(lang: str) -> tuple[tuple[str, float], ...]:
    """Return (verb, zipf) rows from the committed census CSV."""
    path = CENSUS_DIR / f"{lang}.csv"
    if not path.exists():
        return ()
    rows: list[tuple[str, float]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["verb"], float(row["zipf"])))
    return tuple(rows)


def in_census(verb: str, lang: str) -> bool:
    """Whether *verb* appears in the committed corpus census for *lang*."""
    return any(v == verb for v, _ in _load_census(lang))


def verbs_in_tier(tier_name: Tier, lang: str) -> list[str]:
    """All census verbs in *tier_name*, sorted by Zipf descending."""
    matched = [
        (verb, z) for verb, z in _load_census(lang)
        if tier_from_zipf(z, lang) == tier_name
    ]
    matched.sort(key=lambda row: -row[1])
    return [verb for verb, _ in matched]


def filter_by_tier(candidates: list[str], tier_name: Tier, lang: str) -> list[str]:
    """Filter an arbitrary candidate list to verbs in *tier_name*."""
    return [v for v in candidates if tier(v, lang) == tier_name]


def sample_verbs(
    tier_name: Tier,
    lang: str,
    n: int = 5,
    *,
    exclude: frozenset[str] | set[str] | None = None,
    irregular: bool | None = None,
    tense: str = "present",
    person: str = "1st",
    number: str = "singular",
    rng: random.Random | None = None,
) -> list[str]:
    """Sample *n* census verbs from *tier_name*.

    Parameters
    ----------
    exclude:
        Verbs to skip (e.g. ones already used in a benchmark).
    irregular:
        If set and lang is Spanish, keep only verbs where
        ``is_irregular(verb, tense, ...)`` matches this value.
    """
    if n <= 0:
        return []
    excluded = exclude or set()
    candidates = [v for v in verbs_in_tier(tier_name, lang) if v not in excluded]
    if irregular is not None and lang == "es":
        candidates = [
            v for v in candidates
            if is_irregular(v, tense, lang, person, number) is irregular
        ]
    if len(candidates) <= n:
        return candidates
    picker = rng or random.Random()
    return picker.sample(candidates, n)


# Regular Spanish endings for tenses used by our benchmarks. Keys match
# `_ES_TENSE_MAP`. Each value maps (person, number) -> ending applied to the
# stem (for future/conditional the "stem" is the full infinitive).
_ES_REGULAR_ENDINGS: dict[str, dict[str, dict[tuple[str, str], str]]] = {
    "present": {
        "ar": {
            ("1st", "singular"): "o", ("2nd", "singular"): "as", ("3rd", "singular"): "a",
            ("1st", "plural"): "amos", ("2nd", "plural"): "áis", ("3rd", "plural"): "an",
        },
        "er": {
            ("1st", "singular"): "o", ("2nd", "singular"): "es", ("3rd", "singular"): "e",
            ("1st", "plural"): "emos", ("2nd", "plural"): "éis", ("3rd", "plural"): "en",
        },
        "ir": {
            ("1st", "singular"): "o", ("2nd", "singular"): "es", ("3rd", "singular"): "e",
            ("1st", "plural"): "imos", ("2nd", "plural"): "ís", ("3rd", "plural"): "en",
        },
    },
    "preterite": {
        "ar": {
            ("1st", "singular"): "é", ("2nd", "singular"): "aste", ("3rd", "singular"): "ó",
            ("1st", "plural"): "amos", ("2nd", "plural"): "asteis", ("3rd", "plural"): "aron",
        },
        "er": {
            ("1st", "singular"): "í", ("2nd", "singular"): "iste", ("3rd", "singular"): "ió",
            ("1st", "plural"): "imos", ("2nd", "plural"): "isteis", ("3rd", "plural"): "ieron",
        },
        "ir": {
            ("1st", "singular"): "í", ("2nd", "singular"): "iste", ("3rd", "singular"): "ió",
            ("1st", "plural"): "imos", ("2nd", "plural"): "isteis", ("3rd", "plural"): "ieron",
        },
    },
    "imperfect": {
        "ar": {
            ("1st", "singular"): "aba", ("2nd", "singular"): "abas", ("3rd", "singular"): "aba",
            ("1st", "plural"): "ábamos", ("2nd", "plural"): "abais", ("3rd", "plural"): "aban",
        },
        "er": {
            ("1st", "singular"): "ía", ("2nd", "singular"): "ías", ("3rd", "singular"): "ía",
            ("1st", "plural"): "íamos", ("2nd", "plural"): "íais", ("3rd", "plural"): "ían",
        },
        "ir": {
            ("1st", "singular"): "ía", ("2nd", "singular"): "ías", ("3rd", "singular"): "ía",
            ("1st", "plural"): "íamos", ("2nd", "plural"): "íais", ("3rd", "plural"): "ían",
        },
    },
    "future": {
        # Applied to the whole infinitive, not the stem.
        "*": {
            ("1st", "singular"): "é", ("2nd", "singular"): "ás", ("3rd", "singular"): "á",
            ("1st", "plural"): "emos", ("2nd", "plural"): "éis", ("3rd", "plural"): "án",
        },
    },
    "conditional": {
        "*": {
            ("1st", "singular"): "ía", ("2nd", "singular"): "ías", ("3rd", "singular"): "ía",
            ("1st", "plural"): "íamos", ("2nd", "plural"): "íais", ("3rd", "plural"): "ían",
        },
    },
}


def _regular_es_form(verb: str, tense: str, person: str, number: str) -> str | None:
    """Return the regular-paradigm form; None if the ending / tense is unsupported."""
    endings = _ES_REGULAR_ENDINGS.get(tense)
    if endings is None:
        return None

    if tense in ("future", "conditional"):
        ending = endings["*"].get((person, number))
        return f"{verb}{ending}" if ending else None

    if len(verb) < 3:
        return None
    ending_class = verb[-2:]
    if ending_class not in ("ar", "er", "ir"):
        return None
    stem = verb[:-2]
    ending = endings[ending_class].get((person, number))
    return f"{stem}{ending}" if ending else None


def _actual_es_form(verb: str, tense: str, person: str, number: str) -> str | None:
    """Return the form verbecc actually produces for the given cell."""
    mood_tense = _ES_TENSE_MAP.get(tense)
    if mood_tense is None:
        return None
    pn = _ES_PN_KEYS.get((person, number))
    if pn is None:
        return None

    data = _conjugate_es(verb)
    if data is None:
        return None

    mood, verbecc_tense = mood_tense
    entries = data["moods"].get(mood, {}).get(verbecc_tense, [])
    p_key, n_key = pn
    for entry in entries:
        entry_p = entry.get("p")
        entry_n = entry.get("n")
        # verbecc emits enums for these; compare via their .value.
        entry_p_val = getattr(entry_p, "value", entry_p)
        entry_n_val = getattr(entry_n, "value", entry_n)
        if entry_p_val == p_key and entry_n_val == n_key:
            chunks = entry.get("c", [])
            if chunks:
                return _strip_pronoun(chunks[0])
    return None


def is_irregular(verb: str, tense: str, lang: str,
                 person: str = "1st", number: str = "singular") -> bool:
    """Whether the (*verb*, *tense*, *person*, *number*) cell is irregular.

    Compares verbecc's actual conjugation against the regular-paradigm form.
    Any discrepancy (stem change, orthographic change, fully irregular root)
    counts as irregular for that cell.

    Only implemented for Spanish. English raises NotImplementedError.
    """
    if lang == "en":
        raise NotImplementedError("English irregularity flag is not implemented.")
    if lang != "es":
        raise NotImplementedError(f"is_irregular not implemented for lang={lang!r}")

    regular = _regular_es_form(verb, tense, person, number)
    if regular is None:
        return False
    actual = _actual_es_form(verb, tense, person, number)
    if actual is None:
        return False
    return actual != regular


def score_verb(verb: str, lang: str,
               tenses: tuple[str, ...] = ("present", "preterite", "imperfect", "future", "conditional"),
               person: str = "1st", number: str = "singular") -> dict:
    """One-shot record for the methods-section table.

    Returns::
        {
            'verb': ...,
            'lang': ...,
            'zipf': float,
            'tier': 'high' | 'mid' | 'low',
            'in_census': bool,
            'tenses_irregular': [tense, ...],  # empty for English (not implemented)
        }
    """
    z = verb_zipf(verb, lang)
    t = tier_from_zipf(z, lang)
    census_member = in_census(verb, lang)

    if lang == "es":
        irregular = [tn for tn in tenses if is_irregular(verb, tn, lang, person, number)]
    else:
        irregular = []

    return {
        "verb": verb,
        "lang": lang,
        "zipf": round(z, 3),
        "tier": t,
        "in_census": census_member,
        "tenses_irregular": irregular,
    }
