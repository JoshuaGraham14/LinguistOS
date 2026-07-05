"""Build the full verb census used to define frequency tiers.

Scans wordfreq's top-N tokens per language, keeps validated verb infinitives,
scores each with lemma-summed Zipf, and writes:

- ``research/evaluation/lexicon/census/{lang}.csv``  (verb, zipf)
- ``research/evaluation/lexicon/census/{lang}_meta.yaml`` (stats + cutoffs)

Spanish: all non-predicted verbecc verbs in wordfreq top-30k (~1,180).
English: seed-list verbs appearing in wordfreq top-30k, plus regular-verb
heuristic matches (token where both ``{token}ing`` and ``{token}ed`` appear).

Usage::

    python -m research.scripts.build_verb_census
"""

from __future__ import annotations

import csv
import logging
import statistics
from pathlib import Path

import yaml
from wordfreq import top_n_list, word_frequency

logging.getLogger("verbecc").setLevel(logging.WARNING)

OUT_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "lexicon" / "census"

SEARCH_TOP_N = 30_000

# Same seed as before, used as a filter/heuristic for English verbiness.
_EN_VERB_SEED: frozenset[str] = frozenset("""
    be have do say make go take come see get know think want give use find
    tell ask work seem feel try leave call keep let begin help talk turn start
    show hear play run move like live believe hold bring happen write provide
    sit stand lose pay meet include continue set learn change lead understand
    watch follow stop create speak read allow add spend grow open walk win
    offer remember love consider appear buy wait serve die send expect build
    stay fall cut reach kill remain suggest raise pass sell require report
    decide pull carry break receive agree support hit produce eat cover catch
    draw choose cause point describe reflect return determine identify treat
    reduce establish involve compare consist relate depend deal recognise
    represent contain remove attend achieve arrange perform prepare protect
    reveal search share suffer travel wonder answer arrive assume care
    complete concern connect contact defend design divide encourage engage
    ensure enter examine exchange exist explain expose face fail favour fear
    fight finish force gather generate handle imagine improve indicate insist
    intend introduce invite join lay lie listen manage mark mention notice
    observe obtain occur order pick plan please prove publish push realise
    refer reflect refuse regard release repeat replace reply rest result rise
    save seek separate settle share shoot sign sing smile solve sort speak
    spread stare step store stretch strike struggle succeed suffer suggest
    supply survive teach tend test threaten throw touch train trust turn
    understand use vote wait wake walk want warn wash waste watch wave wear
    weigh welcome win wonder work worry write yield knock swing shake
    seek escape climb press swim sleep dream dance cook drive fly float sink
    ride cross march wander crawl creep leap dive borrow lend earn spend
    complain apologise argue debate discuss negotiate whisper shout scream
    cry laugh nod smile grin frown blink wink sneeze cough sigh yawn
    gainsay beseech smite shrive
""".split())

_EN_NOUN_SUFFIXES = (
    "tion", "sion", "ness", "ment", "ity", "ism", "ist", "ship", "hood", "ance", "ence",
)


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


def _looks_like_english_verb(token: str) -> bool:
    if token in _EN_VERB_SEED:
        return True
    if len(token) < 3 or not token.isalpha():
        return False
    if any(token.endswith(s) for s in _EN_NOUN_SUFFIXES):
        return False
    return (
        word_frequency(f"{token}ing", "en") > 0
        and word_frequency(f"{token}ed", "en") > 0
    )


def _build_spanish() -> list[tuple[str, float]]:
    from verbecc import CompleteConjugator  # type: ignore[import-untyped]

    from research.evaluation.lexicon.frequency import verb_zipf

    conjugator = CompleteConjugator(lang="es")
    seen: set[str] = set()
    rows: list[tuple[str, float]] = []

    for token in top_n_list("es", SEARCH_TOP_N):
        if token in seen or " " in token:
            continue
        if not (token.endswith("ar") or token.endswith("er") or token.endswith("ir")):
            continue
        try:
            data = conjugator.conjugate(token).get_data()
        except Exception:
            continue
        verb_info = data.get("verb", {})
        if verb_info.get("predicted", True):
            continue
        if verb_info.get("infinitive") != token:
            continue
        seen.add(token)
        rows.append((token, round(verb_zipf(token, "es"), 3)))

    rows.sort(key=lambda r: -r[1])
    return rows


def _build_english() -> list[tuple[str, float]]:
    from research.evaluation.lexicon.frequency import verb_zipf

    seen: set[str] = set()
    rows: list[tuple[str, float]] = []

    for token in top_n_list("en", SEARCH_TOP_N):
        if token in seen or " " in token:
            continue
        if not _looks_like_english_verb(token):
            continue
        seen.add(token)
        rows.append((token, round(verb_zipf(token, "en"), 3)))

    rows.sort(key=lambda r: -r[1])
    return rows


def _write_lang(lang: str, rows: list[tuple[str, float]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{lang}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["verb", "zipf"])
        writer.writerows(rows)

    scores = sorted(z for _, z in rows)
    p33 = _quantile(scores, 1 / 3)
    p67 = _quantile(scores, 2 / 3)
    meta = {
        "lang": lang,
        "n_verbs": len(rows),
        "search_top_n": SEARCH_TOP_N,
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
            "Verbs outside the census are scored via the same Zipf function "
            "and compared against these frozen boundaries."
        ),
    }
    meta_path = OUT_DIR / f"{lang}_meta.yaml"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")

    print(f"Wrote {len(rows)} verbs -> {csv_path}")
    print(f"  cutoffs: low < {p33:.3f}, high >= {p67:.3f}")
    print(f"  range:   {min(scores):.3f} .. {max(scores):.3f}")


def main() -> None:
    _write_lang("es", _build_spanish())
    _write_lang("en", _build_english())


if __name__ == "__main__":
    main()
