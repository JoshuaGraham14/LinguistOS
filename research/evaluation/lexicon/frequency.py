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
   distribution over a fixed reference verb list per language. Values are
   computed once by `research/scripts/compute_tier_cutoffs.py` and frozen
   in `TIER_CUTOFFS` below. Freezing = pre-registration.

5. **Irregularity is tense-specific**: `is_irregular(verb, tense)` compares
   verbecc's actual conjugation against the regular-paradigm form derived
   from hand-coded Spanish endings. Reflects that Spanish irregularity
   attaches to (verb, tense), not to the verb as a whole
   (e.g. 'tener' is irregular in present indicative, regular in imperfect).

English handling is minimal: `verb_zipf` and `tier` work, but
`is_irregular` raises `NotImplementedError`.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Literal

from wordfreq import word_frequency

logging.getLogger("verbecc").setLevel(logging.WARNING)

Tier = Literal["common", "mid", "rare"]

# Frozen 33rd / 67th percentile Zipf-lemma cutoffs per language.
#
# Provenance: computed once by `research/scripts/compute_tier_cutoffs.py`
# over the reference verb-lemma lists in
# `research/evaluation/lexicon/reference_lemmas/{lang}.txt` (500 Spanish and
# 290 English verb infinitives, drawn from wordfreq's top-30k tokens).
#
# Interpretation: a verb is 'rare' relative to the reference distribution of
# already-common verbs, i.e. bottom-tercile among top-500 Spanish verbs. Verbs
# outside the reference list therefore score as 'rare' by construction.
#
# Regenerate with: python -m research.scripts.compute_tier_cutoffs
TIER_CUTOFFS: dict[str, tuple[float, float]] = {
    "es": (4.665, 5.048),  # n=500, mean=4.93, median=4.83, min=4.04, max=7.21
    "en": (4.999, 5.382),  # n=290, mean=5.17, median=5.17, min=3.47, max=6.80
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


def tier(verb: str, lang: str) -> Tier:
    """Return the frequency tier for *verb* in *lang*.

    Cutoffs come from `TIER_CUTOFFS[lang]` (33rd / 67th Zipf percentiles over
    a reference verb list, frozen at module load time).
    """
    z = verb_zipf(verb, lang)
    rare_upper, common_lower = TIER_CUTOFFS.get(lang, (0.0, 0.0))
    if z < rare_upper:
        return "rare"
    if z >= common_lower:
        return "common"
    return "mid"


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
            'tier': 'common' | 'mid' | 'rare',
            'tenses_irregular': [tense, ...],  # empty for English (not implemented)
        }
    """
    z = verb_zipf(verb, lang)
    rare_upper, common_lower = TIER_CUTOFFS.get(lang, (0.0, 0.0))
    if z < rare_upper:
        t: Tier = "rare"
    elif z >= common_lower:
        t = "common"
    else:
        t = "mid"

    if lang == "es":
        irregular = [tn for tn in tenses if is_irregular(verb, tn, lang, person, number)]
    else:
        irregular = []

    return {
        "verb": verb,
        "lang": lang,
        "zipf": round(z, 3),
        "tier": t,
        "tenses_irregular": irregular,
    }
