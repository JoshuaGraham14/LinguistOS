"""WordNet verb lemmas for building the English verb census."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_LEMMA_FILE = Path(__file__).resolve().parent / "wordnet_verb_lemmas.txt"


def _ensure_wordnet() -> None:
    import ssl

    import nltk

    try:
        from nltk.corpus import wordnet as wn

        wn.synsets("dog")
        return
    except LookupError:
        pass

    # macOS Python installs often lack SSL certs for nltk.org downloads.
    try:
        _ctx = ssl._create_unverified_context
    except AttributeError:
        _ctx = None
    else:
        ssl._create_default_https_context = _ctx  # type: ignore[assignment]

    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)


def _load_from_wordnet() -> frozenset[str]:
    _ensure_wordnet()
    from nltk.corpus import wordnet as wn

    lemmas: set[str] = set()
    for synset in wn.all_synsets("v"):
        for lemma in synset.lemmas():
            name = lemma.name().replace("_", " ").lower()
            if " " in name:
                continue
            if not name.isalpha():
                continue
            if len(name) < 2:
                continue
            lemmas.add(name)
    return frozenset(lemmas)


def _load_from_file() -> frozenset[str]:
    if not _LEMMA_FILE.exists():
        raise FileNotFoundError(
            f"WordNet lemma file missing: {_LEMMA_FILE}. "
            "Run build_verb_census on a machine with NLTK WordNet, or "
            "commit wordnet_verb_lemmas.txt."
        )
    return frozenset(
        line.strip() for line in _LEMMA_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


@lru_cache(maxsize=1)
def wordnet_verb_lemmas() -> frozenset[str]:
    """Single-token English verb lemmas from WordNet (lowercased).

    Uses NLTK WordNet when available; falls back to the committed
    ``wordnet_verb_lemmas.txt`` snapshot for offline/cluster builds.
    """
    try:
        return _load_from_wordnet()
    except Exception:
        return _load_from_file()
