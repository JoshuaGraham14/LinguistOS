"""Token-count bands for sentence_length generation parameter."""

from __future__ import annotations

import random

LENGTH_BANDS: dict[str, tuple[int, int]] = {
    "short": (2, 5),
    # Welsh periphrastic teacher regen: aux+particle+VN already uses ~3 tokens,
    # so short (2–5) collapses to frame-only clauses; 4–8 leaves room for content.
    "short_expanded": (4, 8),
    "medium": (5, 9),
    "long": (10, 16),
}

RANDOM_LENGTH = "random"
# Resolve short vs short_expanded from the cell's construction (Welsh LoRA).
BY_CONSTRUCTION_LENGTH = "by_construction"
# Random draws stay on the original three bands (not short_expanded).
FIXED_LENGTH_LABELS: frozenset[str] = frozenset({"short", "medium", "long"})


def band_label(sentence_length: str) -> str:
    """Return a human-readable band label for prompts (word counts)."""
    lo, hi = get_band(sentence_length)
    return f"{sentence_length} ({lo}–{hi} words)"


def get_band(sentence_length: str) -> tuple[int, int]:
    """Return (min_words, max_words) for a fixed length label."""
    if sentence_length not in LENGTH_BANDS:
        raise ValueError(
            f"Unknown sentence_length {sentence_length!r}; "
            f"expected one of {sorted(LENGTH_BANDS)} or {RANDOM_LENGTH!r}"
        )
    return LENGTH_BANDS[sentence_length]


def sentence_length_for_construction(construction: str | None) -> str:
    """Welsh: periphrastic uses 4–8 words; synthetic (and Spanish) keep 2–5."""
    if str(construction or "").strip().casefold() == "periphrastic":
        return "short_expanded"
    return "short"


def resolve_length_band(
    sentence_length: str,
    *,
    rng: random.Random | None = None,
    construction: str | None = None,
) -> str:
    """Return a fixed band; draw short/medium/long when *sentence_length* is random.

    ``by_construction`` maps periphrastic → ``short_expanded``, else ``short``.
    """
    if sentence_length == RANDOM_LENGTH:
        draw_rng = rng if rng is not None else random.Random()
        return draw_rng.choice(sorted(FIXED_LENGTH_LABELS))
    if sentence_length == BY_CONSTRUCTION_LENGTH:
        return sentence_length_for_construction(construction)
    get_band(sentence_length)
    return sentence_length


def token_count_in_band(count: int, sentence_length: str) -> bool:
    """True when *count* falls within the band for *sentence_length*."""
    lo, hi = get_band(sentence_length)
    return lo <= count <= hi
