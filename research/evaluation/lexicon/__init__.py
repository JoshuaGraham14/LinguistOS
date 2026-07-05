"""Lexicon-level utilities: objective verb frequency, rarity tiers, and irregularity flags.

Introduced to replace LLM-generated 'common/rare' labels with corpus-derived,
per-language Zipf frequencies, following supervisor feedback (22 June 2026).
"""

from research.evaluation.lexicon.frequency import (
    TIER_CUTOFFS,
    is_irregular,
    score_verb,
    tier,
    verb_zipf,
)

__all__ = [
    "TIER_CUTOFFS",
    "is_irregular",
    "score_verb",
    "tier",
    "verb_zipf",
]
