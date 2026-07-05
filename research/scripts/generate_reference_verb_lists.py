"""Generate reference verb-lemma lists used to freeze tier cutoffs.

Writes ``research/evaluation/lexicon/reference_lemmas/{es,en}.txt``.

Spanish
-------
Take wordfreq's top-N Spanish tokens, keep those that verbecc recognises as
a real verb infinitive (``predicted=False``, meaning the verb is in the
conjugation lookup rather than being ML-imputed), cap at ``ES_TARGET_SIZE``.

English
-------
Take wordfreq's top-N English tokens and intersect with a curated seed list
of common English verb infinitives (see :data:`_EN_VERB_SEED`). This is
coarser than the Spanish path, but English is peripheral to the project's
core Spanish analysis, and the resulting list is only used to derive
tier-cutoff percentiles.

Usage
-----
::

    python -m research.scripts.generate_reference_verb_lists
"""

from __future__ import annotations

import logging
from pathlib import Path

from wordfreq import top_n_list

logging.getLogger("verbecc").setLevel(logging.WARNING)

OUT_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "lexicon" / "reference_lemmas"

ES_TARGET_SIZE = 500
ES_SEARCH_TOP_N = 30_000
EN_TARGET_SIZE = 300
EN_SEARCH_TOP_N = 30_000


# Curated seed of common English verb infinitives, kept intentionally coarse.
# Only used as a filter over wordfreq's top-N; extra entries not appearing
# in the wordfreq list are silently dropped.
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
    weigh welcome win wonder work worry write yield write knock swing shake
    seek escape climb press swim sleep dream dance cook drive fly float sink
    ride cross march wander crawl creep leap dive borrow lend earn spend
    complain apologise argue debate discuss negotiate whisper shout scream
    cry laugh nod smile grin frown blink wink sneeze cough sigh yawn
""".split())


def _build_spanish_list() -> list[str]:
    from verbecc import CompleteConjugator  # type: ignore[import-untyped]

    conjugator = CompleteConjugator(lang="es")
    out: list[str] = []
    seen: set[str] = set()

    for token in top_n_list("es", ES_SEARCH_TOP_N):
        if len(out) >= ES_TARGET_SIZE:
            break
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
        out.append(token)

    return out


def _build_english_list() -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in top_n_list("en", EN_SEARCH_TOP_N):
        if len(out) >= EN_TARGET_SIZE:
            break
        if token in seen or token not in _EN_VERB_SEED:
            continue
        seen.add(token)
        out.append(token)
    return out


def _write(path: Path, lemmas: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lemmas) + "\n", encoding="utf-8")


def main() -> None:
    es_lemmas = _build_spanish_list()
    en_lemmas = _build_english_list()

    _write(OUT_DIR / "es.txt", es_lemmas)
    _write(OUT_DIR / "en.txt", en_lemmas)

    print(f"Wrote {len(es_lemmas)} Spanish lemmas to {OUT_DIR / 'es.txt'}")
    print(f"Wrote {len(en_lemmas)} English lemmas to {OUT_DIR / 'en.txt'}")


if __name__ == "__main__":
    main()
