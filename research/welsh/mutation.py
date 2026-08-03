"""Welsh initial soft mutation (treiglad meddal).

Used for periphrastic past (*gwneud* + verbnoun): the verbnoun soft-mutates.
Eurfa stores the radical verbnoun only; mutated gold is derived here.
"""

from __future__ import annotations

# Longest-first so digraphs win over single letters.
_SOFT_RULES: tuple[tuple[str, str], ...] = (
    ("ll", "l"),
    ("rh", "r"),
    ("ph", "ph"),  # no change; keep explicit
    ("th", "th"),
    ("ch", "ch"),
    ("ng", "ng"),
    ("p", "b"),
    ("t", "d"),
    ("c", "g"),
    ("b", "f"),
    ("d", "dd"),
    ("g", ""),
    ("m", "f"),
)


def soft_mutate(word: str) -> str:
    """Apply soft mutation to the initial of ``word`` (Welsh orthography)."""
    if not word:
        return word
    was_title = word[0].isupper() and not word.isupper()
    probe = word.lower()
    for src, dst in _SOFT_RULES:
        if probe.startswith(src):
            out = dst + probe[len(src) :]
            if was_title and out:
                out = out[0].upper() + out[1:]
            return out
    return word


def soft_mutate_alts(word: str, extra: list[str] | None = None) -> list[str]:
    """Primary soft-mutated form plus optional extras (deduped, primary first)."""
    primary = soft_mutate(word)
    out: list[str] = []
    for w in [primary, *(extra or [])]:
        if w and w not in out:
            out.append(w)
    return out
