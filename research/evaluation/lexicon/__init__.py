"""Lexicon-level utilities: objective verb frequency, rarity tiers, and irregularity flags.

Introduced to replace LLM-generated labels with corpus-derived, per-language
Zipf frequencies, following supervisor feedback (22 June 2026).
"""

from research.evaluation.lexicon.frequency import (
    TIER_CUTOFFS,
    filter_by_tier,
    in_census,
    is_irregular,
    sample_verbs,
    score_verb,
    tier,
    tier_from_zipf,
    verb_zipf,
    verbs_in_tier,
)

__all__ = [
    "TIER_CUTOFFS",
    "filter_by_tier",
    "in_census",
    "is_irregular",
    "sample_verbs",
    "score_verb",
    "tier",
    "tier_from_zipf",
    "verb_zipf",
    "verbs_in_tier",
]
