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


@dataclass
class _LiveBeam:
    """Internal beam member with KV cache for incremental decoding."""

    generated_ids: list[int]
    log_prob: float
    tracker: ClauseTracker
    past_key_values: Any
    finished: bool = False

    def to_scored(self, lambda_: float) -> ScoredHypothesis:
        return ScoredHypothesis(
            token_ids=tuple(self.generated_ids),
            log_prob=self.log_prob,
            score=neurologic_score(self.log_prob, self.tracker, lambda_),
            tracker=self.tracker,
            finished=self.finished,
        )


def _clone_past(past_key_values: Any) -> Any:
    """Clone a HF past_key_values / DynamicCache tree for branching beam children."""
    if past_key_values is None:
        return None
    import copy

    return copy.deepcopy(past_key_values)


def neurologic_generate_one(
    model_id: str,
    *,
    system: str,
    user: str,
    expected_form: str,
    morph_ban_set: MorphBanSet | None,
    num_beams: int = 8,
    max_new_tokens: int = 80,
    neurologic_lambda: float = DEFAULT_NEUROLOGIC_LAMBDA,
    neurologic_alpha: int = DEFAULT_NEUROLOGIC_ALPHA,
) -> str:
    """Run clause-aware beam search for a single chat prompt (no cross-cell batching)."""
    import torch
    import torch.nn.functional as F

    from research.generation.baseline_hf import (
        ChatGenerationSpec,
        _chat_template_text,
        _load_model,
        _strip_thinking,
        record_cost_telemetry,
    )

    if num_beams <= 0:
        raise ValueError(f"num_beams must be positive, got {num_beams}")
    if neurologic_alpha <= 0:
        raise ValueError(f"neurologic_alpha must be positive, got {neurologic_alpha}")

    tokenizer, model = _load_model(model_id)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    eos_id = tokenizer.eos_token_id

    text = _chat_template_text(
        tokenizer,
        model_id,
        ChatGenerationSpec(system=system, user=user, max_new_tokens=max_new_tokens),
    )
    prompt = tokenizer(text, return_tensors="pt")
    prompt_ids = prompt["input_ids"].to(model.device)
    prompt_width = int(prompt_ids.shape[1])
    record_cost_telemetry([prompt_width])

    base_tracker = ClauseTracker.from_forms(tokenizer, expected_form, morph_ban_set)

    with torch.no_grad():
        out = model(input_ids=prompt_ids, use_cache=True)
        logits = out.logits[0, -1]
        past = out.past_key_values
        log_probs = F.log_softmax(logits.float(), dim=-1)
        top_alpha = min(neurologic_alpha, log_probs.shape[-1])
        values, indices = torch.topk(log_probs, k=top_alpha)

        expansions: list[ScoredHypothesis] = []
        live_by_key: dict[tuple[int, ...], _LiveBeam] = {}
        for val, idx in zip(values.tolist(), indices.tolist()):
            token_id = int(idx)
            tracker = base_tracker.clone()
            tracker.append(token_id)
            hyp = _LiveBeam(
                generated_ids=[token_id],
                log_prob=float(val),
                tracker=tracker,
                past_key_values=_clone_past(past),
                finished=(token_id == eos_id),
            )
            scored = hyp.to_scored(neurologic_lambda)
            expansions.append(scored)
            live_by_key[scored.token_ids] = hyp

        pruned = prune_irreversible(expansions)
        if not pruned:
            # Empty-beam fallback: keep best pre-prune candidate.
            pruned = sorted(expansions, key=lambda c: c.score, reverse=True)[:1]
        selected = select_diverse_beam(pruned, num_beams=num_beams)
        beam: list[_LiveBeam] = []
        for scored in selected:
            live = live_by_key[scored.token_ids]
            # Advance KV cache with the chosen first token.
            token_tensor = torch.tensor([[scored.token_ids[-1]]], device=model.device)
            step_out = model(
                input_ids=token_tensor,
                past_key_values=live.past_key_values,
                use_cache=True,
            )
            live.past_key_values = step_out.past_key_values
            # Stash next-step logits on the object for the loop below.
            live._next_log_probs = F.log_softmax(step_out.logits[0, -1].float(), dim=-1)  # type: ignore[attr-defined]
            beam.append(live)

        for _step in range(1, max_new_tokens):
            if all(h.finished for h in beam):
                break

            expansions = []
            live_by_key = {}
            fallback_pool: list[ScoredHypothesis] = []

            for parent in beam:
                if parent.finished:
                    scored = parent.to_scored(neurologic_lambda)
                    expansions.append(scored)
                    live_by_key[scored.token_ids] = parent
                    fallback_pool.append(scored)
                    continue

                log_probs = parent._next_log_probs  # type: ignore[attr-defined]
                top_alpha = min(neurologic_alpha, log_probs.shape[-1])
                values, indices = torch.topk(log_probs, k=top_alpha)
                for val, idx in zip(values.tolist(), indices.tolist()):
                    token_id = int(idx)
                    tracker = parent.tracker.clone()
                    tracker.append(token_id)
                    child = _LiveBeam(
                        generated_ids=[*parent.generated_ids, token_id],
                        log_prob=parent.log_prob + float(val),
                        tracker=tracker,
                        past_key_values=parent.past_key_values,
                        finished=(token_id == eos_id),
                    )
                    scored = child.to_scored(neurologic_lambda)
                    expansions.append(scored)
                    live_by_key[scored.token_ids] = child
                    fallback_pool.append(scored)

            pruned = prune_irreversible(expansions)
            if not pruned:
                pruned = sorted(fallback_pool, key=lambda c: c.score, reverse=True)[:num_beams]

            selected = select_diverse_beam(pruned, num_beams=num_beams)
            new_beam: list[_LiveBeam] = []
            for scored in selected:
                live = live_by_key[scored.token_ids]
                if live.finished:
                    new_beam.append(live)
                    continue
                # Branch KV: clone parent past then feed the new token.
                # Children that share a parent currently share the same past
                # reference until we clone on consume.
                past = _clone_past(live.past_key_values)
                token_tensor = torch.tensor([[scored.token_ids[-1]]], device=model.device)
                step_out = model(
                    input_ids=token_tensor,
                    past_key_values=past,
                    use_cache=True,
                )
                live.past_key_values = step_out.past_key_values
                live._next_log_probs = F.log_softmax(  # type: ignore[attr-defined]
                    step_out.logits[0, -1].float(), dim=-1
                )
                new_beam.append(live)
            beam = new_beam

    final = pick_final_hypothesis([h.to_scored(neurologic_lambda) for h in beam])
    if final is None:
        return ""
    raw = tokenizer.decode(list(final.token_ids), skip_special_tokens=True)
    return _strip_thinking(raw)
