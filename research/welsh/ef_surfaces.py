"""General Welsh surface expansions for expected-form matching.

These rules are **lemma-agnostic** (or conjugation-class-general) so they
transfer to held-out / OOD verbs:

- colloquial + soft-mutated **auxiliaries** (shared across all peri verbs)
- **accent / diaeresis folding** for token comparison
- **``-oi`` verb** finite orthographic variants (``paratoi``, ``troi``, …)
"""

from __future__ import annotations

from typing import Iterable

from research.welsh.mutation import soft_mutate

# Circumflex + diaeresis vowels commonly varied in Welsh orthography.
_WELSH_ACCENT_FOLD = str.maketrans(
    {
        "â": "a",
        "ê": "e",
        "î": "i",
        "ô": "o",
        "û": "u",
        "ŵ": "w",
        "ŷ": "y",
        "ä": "a",
        "ë": "e",
        "ï": "i",
        "ö": "o",
        "ü": "u",
        "ÿ": "y",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
    }
)


def fold_welsh_accents(token: str) -> str:
    """Case-fold and strip Welsh vowel diacritics for comparison."""
    return token.casefold().translate(_WELSH_ACCENT_FOLD)


# Spoken / soft surfaces for common finite auxiliaries.
# Keys are accent-folded casefold forms of the literary citation.
_COLLOQUIAL_AUX: dict[str, tuple[str, ...]] = {
    "rwyf": ("dw", "ydw", "rwy", "wi", "ydwyf", "wyf"),
    "rwyt": ("wyt",),
    "rydym": ("rydyn", "dyn", "dan", "ydyn", "ydym", "ym"),
    "rydych": ("dych", "dach", "ydych", "ych"),
    "mae": ("ydy", "yw"),
    "maen": ("ydyn",),
    "roeddwn": ("oeddwn", "o'n"),
    "roeddet": ("oeddet", "oeddit", "roeddit"),
    "roedd": ("oedd",),
    "roeddem": ("roedden", "oeddem", "oeddan", "oedden"),
    "roeddech": ("oeddech",),
    "roedden": ("oedden", "oeddent", "oeddynt"),
    "gwnes": ("wnes", "nes", "gwneuthum", "gwnaes"),
    "gwnest": ("wnest", "nest", "gwnest", "gwnaethost"),
    "gwnaethom": ("wnaethom", "wnaethon", "naethom", "gwnaethon"),
    "gwnaethoch": ("wnaethoch", "naethoch", "gwnaesoch"),
    "gwnaethon": ("wnaethon", "naethon", "gwnaethant"),
    "nath": ("wnaeth", "naeth", "gwnaeth"),
    "byddaf": ("bydda",),
    "byddi": ("byddi",),
    "byddwn": ("byddwn",),
    "byddwch": ("byddwch",),
}


def expand_aux_surfaces(aux: str, alts: Iterable[str] | None = None) -> list[str]:
    """Gold aux + YAML alts + colloquial / soft-mutated companions."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(form: str | None) -> None:
        if not form:
            return
        text = str(form).strip()
        if not text:
            return
        key = fold_welsh_accents(text)
        if key in seen:
            return
        seen.add(key)
        out.append(text)

    bases = [aux, *(alts or [])]
    for base in bases:
        _add(base)
        if not base:
            continue
        key = fold_welsh_accents(str(base))
        for colloq in _COLLOQUIAL_AUX.get(key, ()):
            _add(colloq)
            _add(soft_mutate(colloq))
        _add(soft_mutate(str(base).strip()))
    return out


def _is_oi_lemma(lemma: str) -> bool:
    return fold_welsh_accents(lemma).endswith("oi")


def _oi_stems(lemma: str) -> set[str]:
    """Likely conjugated stems for an ``-oi`` verbnoun."""
    base = fold_welsh_accents(lemma)
    if not base.endswith("oi"):
        return set()
    # troi → {troi, tro}; paratoi → {paratoi, parato, parat}
    stems = {base, base[:-1], base[:-2]}
    return {s for s in stems if len(s) >= 2}


def expand_oi_form_variants(form: str, *, lemma: str = "") -> list[str]:
    """Finite orthographic variants for Welsh verbs whose lemma ends in ``-oi``.

    Accepts common literary↔colloquial / contracted↔full endings, e.g.::

        paratof → paratoaf
        trois → troais
        trown → troiwn
        trôi → troai
        paratôn → paratoant / paratoiant

    Does not invent variants for the bare verbnoun (``form == lemma``).
    When ``lemma`` is set, only expands forms that share an ``-oi`` stem prefix
    (so ``trois`` is not treated as a ``rhoi`` variant).
    """
    form = (form or "").strip()
    if not form:
        return []
    lemma = (lemma or "").strip()
    if lemma and not _is_oi_lemma(lemma):
        return [form]
    # Bare VN / identical citation: no finite expansions.
    if lemma and form.casefold() == lemma.casefold():
        return [form]
    if lemma:
        stems = _oi_stems(lemma)
        folded_form = fold_welsh_accents(form)
        if not any(folded_form.startswith(s) for s in stems):
            return [form]

    out: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> None:
        text = text.strip()
        if not text:
            return
        key = fold_welsh_accents(text)
        if key in seen:
            return
        seen.add(key)
        out.append(text)

    _add(form)
    base = fold_welsh_accents(form)

    # Longest-first suffix rewrites on the accent-folded surface.
    expansions: list[tuple[str, tuple[str, ...]]] = [
        ("oaist", ()),
        ("oais", ()),
        ("oaf", ()),
        ("oiwch", ()),
        ("oiwn", ()),
        ("oiant", ()),
        ("oant", ()),
        ("oist", ("oaist",)),
        ("ois", ("oais",)),
        ("owch", ("oiwch",)),
        ("own", ("oiwn",)),
        ("ont", ("oant", "oiant")),
        ("of", ("oaf",)),
        ("oai", ()),
        ("on", ("oant", "oiant")),
        ("oi", ("oai",)),
    ]
    for suffix, repls in expansions:
        if not base.endswith(suffix):
            continue
        # Avoid over-short stems (e.g. tiny tokens).
        stem = base[: -len(suffix)]
        if len(stem) < 2:
            continue
        # ``on`` / ``oi`` are aggressive; require a longer stem.
        if suffix in {"on", "oi"} and len(stem) < 3:
            continue
        for rep in repls:
            _add(stem + rep)
        break  # only the longest matching suffix

    return out
