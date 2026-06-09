"""Shared whitespace tokenization for distribution metrics."""

from __future__ import annotations

import string

# string.punctuation omits Spanish inverted marks (¿ ¡).
_STRIP_PUNCT = string.punctuation + "¿¡"


def tokenize(text: str) -> list[str]:
    """Lowercase, strip, split on whitespace, strip punctuation from tokens."""
    cleaned = text.strip().lower()
    if not cleaned:
        return []
    table = str.maketrans("", "", _STRIP_PUNCT)
    return [t for raw in cleaned.split() if (t := raw.translate(table))]
