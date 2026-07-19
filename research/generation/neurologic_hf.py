"""Neurologic-inspired clause-aware beam search for morphology CNF (Direction 4).

Constraint formula per cell (thin morph bans by default):

    D(expected_form) AND NOT D(c) for each competitor / wrong pronoun c

This module replaces HF standard beam + logits processors with prune / group /
select search (Lu et al., NAACL 2021 style), without claiming a full paper
reimplementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from research.generation.constrained_hf import encode_force_variants
from research.generation.morph_bans import MorphBanSet, encode_bad_words

DEFAULT_NEUROLOGIC_LAMBDA = 0.1
DEFAULT_NEUROLOGIC_ALPHA = 50


def _is_contiguous_subsequence(haystack: Sequence[int], needle: Sequence[int]) -> bool:
    if not needle:
        return False
    n = len(needle)
    if n > len(haystack):
        return False
    for i in range(len(haystack) - n + 1):
        if list(haystack[i : i + n]) == list(needle):
            return True
    return False


def _max_prefix_fraction(haystack: Sequence[int], variants: Sequence[Sequence[int]]) -> float:
    """Largest matched prefix length / |variant| over positive variants."""
    best = 0.0
    if not haystack:
        return 0.0
    for variant in variants:
        if not variant:
            continue
        matched = 0
        # Prefer a suffix of haystack that is a prefix of variant (ongoing emit).
        max_k = min(len(haystack), len(variant))
        for k in range(max_k, 0, -1):
            if list(haystack[-k:]) == list(variant[:k]):
                matched = k
                break
        # Also allow an earlier full match start mid-sequence.
        if matched == 0:
            for i in range(len(haystack)):
                k = 0
                while (
                    i + k < len(haystack)
                    and k < len(variant)
                    and haystack[i + k] == variant[k]
                ):
                    k += 1
                if k > matched:
                    matched = k
        best = max(best, matched / len(variant))
    return best


@dataclass
class ClauseTracker:
    """Track gold positive + negative competitor literals on a generated tail."""

    gold_variants: list[list[int]]
    negative_variants: list[list[int]]
    generated_ids: list[int] = field(default_factory=list)
    gold_satisfied: bool = False
    irreversibly_unsatisfied: bool = False

    @classmethod
    def from_forms(
        cls,
        tokenizer: Any,
        expected_form: str,
        morph_ban_set: MorphBanSet | None,
    ) -> ClauseTracker:
        gold = encode_force_variants(tokenizer, expected_form) if expected_form else []
        negatives: list[list[int]] = []
        if morph_ban_set is not None:
            negatives = encode_bad_words(tokenizer, morph_ban_set)
        return cls(gold_variants=gold, negative_variants=negatives)

    def clone(self) -> ClauseTracker:
        return ClauseTracker(
            gold_variants=self.gold_variants,
            negative_variants=self.negative_variants,
            generated_ids=list(self.generated_ids),
            gold_satisfied=self.gold_satisfied,
            irreversibly_unsatisfied=self.irreversibly_unsatisfied,
        )

    def append(self, token_id: int) -> None:
        self.generated_ids.append(int(token_id))
        self._refresh()

    def _refresh(self) -> None:
        if self.irreversibly_unsatisfied:
            return
        for neg in self.negative_variants:
            if _is_contiguous_subsequence(self.generated_ids, neg):
                self.irreversibly_unsatisfied = True
                return
        if not self.gold_satisfied:
            for gold in self.gold_variants:
                if _is_contiguous_subsequence(self.generated_ids, gold):
                    self.gold_satisfied = True
                    return

    @property
    def prefix_frac(self) -> float:
        if self.gold_satisfied:
            return 1.0
        return _max_prefix_fraction(self.generated_ids, self.gold_variants)

    @property
    def satisfied_clause_count(self) -> int:
        # Two clause groups: gold positive, and "no negative violated".
        count = 0
        if self.gold_satisfied:
            count += 1
        if not self.irreversibly_unsatisfied:
            count += 1
        return count


def neurologic_score(log_prob: float, tracker: ClauseTracker, lambda_: float) -> float:
    """Likelihood + λ · max prefix progress toward unsatisfied gold."""
    bonus = 0.0 if tracker.gold_satisfied else tracker.prefix_frac
    return float(log_prob) + float(lambda_) * bonus


@dataclass(frozen=True)
class ScoredHypothesis:
    """One beam candidate after expansion."""

    token_ids: tuple[int, ...]
    log_prob: float
    score: float
    tracker: ClauseTracker
    finished: bool = False


def prune_irreversible(candidates: Sequence[ScoredHypothesis]) -> list[ScoredHypothesis]:
    """Drop candidates that irreversibly violate a negative literal."""
    kept = [c for c in candidates if not c.tracker.irreversibly_unsatisfied]
    return kept


def group_by_gold_fired(
    candidates: Sequence[ScoredHypothesis],
) -> dict[bool, list[ScoredHypothesis]]:
    """Group by whether the gold positive literal is irreversibly satisfied."""
    groups: dict[bool, list[ScoredHypothesis]] = {True: [], False: []}
    for c in candidates:
        groups[bool(c.tracker.gold_satisfied)].append(c)
    return groups


def select_diverse_beam(
    candidates: Sequence[ScoredHypothesis],
    *,
    num_beams: int,
) -> list[ScoredHypothesis]:
    """Round-robin across gold-fired groups, ranked by score within each group."""
    if num_beams <= 0 or not candidates:
        return []

    groups = group_by_gold_fired(candidates)
    ordered_groups: list[list[ScoredHypothesis]] = []
    for key in (True, False):
        bucket = sorted(groups[key], key=lambda c: c.score, reverse=True)
        if bucket:
            ordered_groups.append(bucket)

    if not ordered_groups:
        return []

    # Visit groups in descending order of their best score.
    ordered_groups.sort(key=lambda bucket: bucket[0].score, reverse=True)

    selected: list[ScoredHypothesis] = []
    indices = [0] * len(ordered_groups)
    while len(selected) < num_beams:
        progressed = False
        for g_idx, bucket in enumerate(ordered_groups):
            if indices[g_idx] >= len(bucket):
                continue
            selected.append(bucket[indices[g_idx]])
            indices[g_idx] += 1
            progressed = True
            if len(selected) >= num_beams:
                break
        if not progressed:
            break
    return selected


def pick_final_hypothesis(beam: Sequence[ScoredHypothesis]) -> ScoredHypothesis | None:
    """Among max satisfied-clause count, pick highest likelihood."""
    if not beam:
        return None
    best_sat = max(h.tracker.satisfied_clause_count for h in beam)
    pool = [h for h in beam if h.tracker.satisfied_clause_count == best_sat]
    return max(pool, key=lambda h: h.log_prob)
