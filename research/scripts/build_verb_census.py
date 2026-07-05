"""Build the full verb census used to define frequency tiers.

Scans the **full wordfreq dictionary** per language, keeps validated verb
lemmas, scores each with parallel lemma-summed Zipf, and writes:

- ``research/evaluation/lexicon/census/{lang}.csv``  (verb, zipf)
- ``research/evaluation/lexicon/census/{lang}_meta.yaml`` (stats + cutoffs)

Spanish
    wordfreq ``get_frequency_dict('es')`` tokens ending in ``-ar/-er/-ir``,
    validated as non-predicted dictionary verbs by verbecc.

English
    WordNet verb lemmas (single-token) intersected with the wordfreq dictionary.

Tier cutoffs are the 33rd / 67th percentiles of Zipf-lemma scores within each
census (high / mid / low). Verbs outside the census are still scored via
``verb_zipf()`` and compared against the same frozen boundaries.

Usage::

    python -m research.scripts.build_verb_census
"""

from __future__ import annotations

import csv
import logging
import statistics
from pathlib import Path

import yaml
from wordfreq import get_frequency_dict

logging.getLogger("verbecc").setLevel(logging.WARNING)

OUT_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "lexicon" / "census"


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _is_spanish_verb_candidate(token: str) -> bool:
    return (
        " " not in token
        and len(token) >= 4
        and (token.endswith("ar") or token.endswith("er") or token.endswith("ir"))
        and token.isalpha()
    )


def _build_spanish() -> list[tuple[str, float]]:
    from verbecc import CompleteConjugator  # type: ignore[import-untyped]

    from research.evaluation.lexicon.frequency import verb_zipf

    freq_dict = get_frequency_dict("es", "best")
    candidates = [t for t in freq_dict if _is_spanish_verb_candidate(t)]
    print(f"  Spanish: {len(freq_dict):,} wordfreq tokens, {len(candidates):,} verb-shaped")

    conjugator = CompleteConjugator(lang="es")
    rows: list[tuple[str, float]] = []
    for i, token in enumerate(candidates):
        if i and i % 2000 == 0:
            print(f"    verbecc validated {i:,}/{len(candidates):,}...")
        try:
            data = conjugator.conjugate(token).get_data()
        except Exception:
            continue
        verb_info = data.get("verb", {})
        if verb_info.get("predicted", True):
            continue
        if verb_info.get("infinitive") != token:
            continue
        rows.append((token, round(verb_zipf(token, "es"), 3)))

    rows.sort(key=lambda r: -r[1])
    return rows


def _build_english() -> list[tuple[str, float]]:
    from research.evaluation.lexicon.frequency import verb_zipf
    from research.evaluation.lexicon.wordnet_verbs import wordnet_verb_lemmas

    freq_dict = get_frequency_dict("en", "best")
    wn_verbs = wordnet_verb_lemmas()
    lemmas = sorted(wn_verbs & set(freq_dict.keys()))
    print(f"  English: {len(freq_dict):,} wordfreq tokens, {len(wn_verbs):,} WordNet verb lemmas")
    print(f"           {len(lemmas):,} lemmas in both")

    rows = [(verb, round(verb_zipf(verb, "en"), 3)) for verb in lemmas]
    rows.sort(key=lambda r: -r[1])
    return rows


def _write_lang(lang: str, rows: list[tuple[str, float]], *, verb_source: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{lang}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["verb", "zipf"])
        writer.writerows(rows)

    scores = sorted(z for _, z in rows)
    p33 = _quantile(scores, 1 / 3)
    p67 = _quantile(scores, 2 / 3)
    freq_dict = get_frequency_dict(lang, "best")
    meta = {
        "lang": lang,
        "n_verbs": len(rows),
        "n_wordfreq_tokens": len(freq_dict),
        "verb_source": verb_source,
        "lemma_scoring": (
            "lemma-summed Zipf: Spanish via verbecc present+infinitive+gerund+participle; "
            "English via regular -s/-ed/-ing plus en_irregular.py table"
        ),
        "zipf_min": round(min(scores), 3),
        "zipf_max": round(max(scores), 3),
        "zipf_mean": round(statistics.fmean(scores), 3),
        "zipf_median": round(statistics.median(scores), 3),
        "tier_cutoffs": {
            "low_upper": round(p33, 3),
            "high_lower": round(p67, 3),
        },
        "tier_interpretation": (
            "low = Zipf below 33rd percentile of this census; "
            "high = Zipf at/above 67th percentile; mid = between. "
            "Tiers are for stratified verb selection; Zipf is the continuous "
            "analysis variable. Verbs outside the census use the same Zipf "
            "function and frozen boundaries."
        ),
    }
    meta_path = OUT_DIR / f"{lang}_meta.yaml"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")

    print(f"Wrote {len(rows)} verbs -> {csv_path}")
    print(f"  cutoffs: low < {p33:.3f}, high >= {p67:.3f}")
    print(f"  range:   {min(scores):.3f} .. {max(scores):.3f}")


def main() -> None:
    print("Building Spanish census...")
    es_rows = _build_spanish()
    _write_lang(
        "es",
        es_rows,
        verb_source="wordfreq full dictionary + verbecc-validated -ar/-er/-ir verbs",
    )

    print("\nBuilding English census...")
    en_rows = _build_english()
    _write_lang(
        "en",
        en_rows,
        verb_source="wordfreq full dictionary ∩ WordNet verb lemmas",
    )


if __name__ == "__main__":
    main()
