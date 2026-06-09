"""Token-count bands for sentence_length generation parameter."""

from __future__ import annotations

LENGTH_BANDS: dict[str, tuple[int, int]] = {
    "short": (2, 5),
    "medium": (5, 9),
    "long": (10, 16),
}


def band_label(sentence_length: str) -> str:
    """Return a human-readable band label for prompts."""
    lo, hi = get_band(sentence_length)
    return f"{sentence_length} ({lo}–{hi} tokens)"


def get_band(sentence_length: str) -> tuple[int, int]:
    """Return (min_tokens, max_tokens) for a length label."""
    if sentence_length not in LENGTH_BANDS:
        raise ValueError(
            f"Unknown sentence_length {sentence_length!r}; "
            f"expected one of {sorted(LENGTH_BANDS)}"
        )
    return LENGTH_BANDS[sentence_length]


def token_count_in_band(count: int, sentence_length: str) -> bool:
    """True when *count* falls within the band for *sentence_length*."""
    lo, hi = get_band(sentence_length)
    return lo <= count <= hi
