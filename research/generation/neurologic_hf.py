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

from research.generation.constrained_hf import (
    ConstrainedHFSoftPlainBGenerator,
    encode_force_variants,
)
from research.generation.morph_bans import MorphBanSet, encode_bad_words

DEFAULT_NEUROLOGIC_LAMBDA = 0.1
DEFAULT_NEUROLOGIC_ALPHA = 50


@dataclass
class PrefixAutomaton:
    """Incremental multi-token sequence matcher (prefix progress + completions).

    Tracks every target sequence in parallel. On each fed token, advances any
    active prefix, restarts on a fresh start-token match, and records newly
    completed sequence indices. Used for gold forms and banned competitors.
    """

    sequences: list[list[int]]
    progress: list[int] = field(default_factory=list)
    completed: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.progress:
            self.progress = [0] * len(self.sequences)

    def clone(self) -> PrefixAutomaton:
        return PrefixAutomaton(
            sequences=self.sequences,
            progress=list(self.progress),
            completed=set(self.completed),
        )

    def feed(self, token_id: int) -> set[int]:
        """Consume one token; return indices newly completed on this step."""
        newly: set[int] = set()
        tok = int(token_id)
        for i, seq in enumerate(self.sequences):
            if not seq or i in self.completed:
                continue
            matched = self.progress[i]
            if matched < len(seq) and seq[matched] == tok:
                matched += 1
                self.progress[i] = matched
                if matched == len(seq):
                    self.completed.add(i)
                    newly.add(i)
                continue
            # Restart if this token begins the sequence.
            if seq[0] == tok:
                self.progress[i] = 1
                if len(seq) == 1:
                    self.completed.add(i)
                    newly.add(i)
            else:
                self.progress[i] = 0
        return newly

    @property
    def max_prefix_fraction(self) -> float:
        best = 0.0
        for i, seq in enumerate(self.sequences):
            if not seq:
                continue
            if i in self.completed:
                return 1.0
            best = max(best, self.progress[i] / len(seq))
        return best

    @property
    def partial_indices(self) -> frozenset[int]:
        return frozenset(
            i
            for i, p in enumerate(self.progress)
            if p > 0 and i not in self.completed
        )


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
    auto = PrefixAutomaton(sequences=[list(v) for v in variants])
    for tok in haystack:
        auto.feed(tok)
        if auto.completed:
            return 1.0
    return auto.max_prefix_fraction


@dataclass
class ClauseTracker:
    """Track gold positive + negative competitor literals on a generated tail."""

    gold_variants: list[list[int]]
    negative_variants: list[list[int]]
    generated_ids: list[int] = field(default_factory=list)
    gold_satisfied: bool = False
    irreversibly_unsatisfied: bool = False
    gold_auto: PrefixAutomaton | None = None
    neg_auto: PrefixAutomaton | None = None
    use_prefix_automaton: bool = True

    def __post_init__(self) -> None:
        if self.use_prefix_automaton:
            if self.gold_auto is None:
                self.gold_auto = PrefixAutomaton(sequences=self.gold_variants)
            if self.neg_auto is None:
                self.neg_auto = PrefixAutomaton(sequences=self.negative_variants)

    @classmethod
    def from_forms(
        cls,
        tokenizer: Any,
        expected_form: str,
        morph_ban_set: MorphBanSet | None,
        *,
        use_prefix_automaton: bool = True,
    ) -> ClauseTracker:
        gold = encode_force_variants(tokenizer, expected_form) if expected_form else []
        negatives: list[list[int]] = []
        if morph_ban_set is not None:
            negatives = encode_bad_words(tokenizer, morph_ban_set)
        return cls(
            gold_variants=gold,
            negative_variants=negatives,
            use_prefix_automaton=use_prefix_automaton,
        )

    def clone(self) -> ClauseTracker:
        return ClauseTracker(
            gold_variants=self.gold_variants,
            negative_variants=self.negative_variants,
            generated_ids=list(self.generated_ids),
            gold_satisfied=self.gold_satisfied,
            irreversibly_unsatisfied=self.irreversibly_unsatisfied,
            gold_auto=self.gold_auto.clone() if self.gold_auto is not None else None,
            neg_auto=self.neg_auto.clone() if self.neg_auto is not None else None,
            use_prefix_automaton=self.use_prefix_automaton,
        )

    def append(self, token_id: int) -> None:
        self.generated_ids.append(int(token_id))
        if self.use_prefix_automaton and self.gold_auto is not None and self.neg_auto is not None:
            self._refresh_automaton(int(token_id))
        else:
            self._refresh_scan()

    def _refresh_automaton(self, token_id: int) -> None:
        assert self.gold_auto is not None and self.neg_auto is not None
        if self.irreversibly_unsatisfied:
            return
        if self.neg_auto.feed(token_id):
            self.irreversibly_unsatisfied = True
            return
        if not self.gold_satisfied and self.gold_auto.feed(token_id):
            self.gold_satisfied = True

    def _refresh_scan(self) -> None:
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
        if self.use_prefix_automaton and self.gold_auto is not None:
            return self.gold_auto.max_prefix_fraction
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

    @property
    def irreversible_sat_key(self) -> frozenset[str]:
        """State key for diverse beam grouping (richer than gold_fired alone)."""
        keys: set[str] = set()
        if self.gold_satisfied:
            keys.add("gold")
        if self.use_prefix_automaton and self.neg_auto is not None:
            for i in self.neg_auto.partial_indices:
                keys.add(f"neg_partial:{i}")
        elif not self.use_prefix_automaton:
            # Scan fallback: approximate with gold-only key.
            pass
        return frozenset(keys)


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


def group_by_clause_state(
    candidates: Sequence[ScoredHypothesis],
) -> dict[frozenset[str], list[ScoredHypothesis]]:
    """Group by irreversible/partial clause-state key (Neurologic-style)."""
    groups: dict[frozenset[str], list[ScoredHypothesis]] = {}
    for c in candidates:
        key = c.tracker.irreversible_sat_key
        groups.setdefault(key, []).append(c)
    return groups


def select_diverse_beam(
    candidates: Sequence[ScoredHypothesis],
    *,
    num_beams: int,
    rich_grouping: bool = False,
) -> list[ScoredHypothesis]:
    """Round-robin across constraint-state groups, ranked by score within each."""
    if num_beams <= 0 or not candidates:
        return []

    if rich_grouping:
        raw_groups = group_by_clause_state(candidates)
        ordered_groups = [
            sorted(bucket, key=lambda c: c.score, reverse=True)
            for bucket in raw_groups.values()
            if bucket
        ]
    else:
        groups = group_by_gold_fired(candidates)
        ordered_groups = []
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
    rich_grouping: bool = False,
    use_prefix_automaton: bool = True,
    min_new_tokens: int = 0,
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

    base_tracker = ClauseTracker.from_forms(
        tokenizer,
        expected_form,
        morph_ban_set,
        use_prefix_automaton=use_prefix_automaton,
    )

    def _eos_allowed(gen_len: int) -> bool:
        return gen_len >= max(0, int(min_new_tokens))

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
            if token_id == eos_id and not _eos_allowed(1):
                continue
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
        selected = select_diverse_beam(
            pruned, num_beams=num_beams, rich_grouping=rich_grouping
        )
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
                next_len = len(parent.generated_ids) + 1
                for val, idx in zip(values.tolist(), indices.tolist()):
                    token_id = int(idx)
                    if token_id == eos_id and not _eos_allowed(next_len):
                        continue
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

            selected = select_diverse_beam(
                pruned, num_beams=num_beams, rich_grouping=rich_grouping
            )
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


class NeurologicHFThinPlainBGenerator(ConstrainedHFSoftPlainBGenerator):
    """Fix B + thin morph CNF via Neurologic-inspired search (no soft λ / hard force)."""

    USE_HARD_CONSTRAINT = False
    _USE_SOFT_BIAS = False
    _USE_MORPH_BANS = True
    _MORPH_BAN_MODE = "thin"
    _MORPH_BAN_SUBJECT_GATE = False
    _MORPH_BAN_SOFT = False
    _REQUIRE_FULL_SENTENCE = True

    def __init__(
        self,
        model: str = "Qwen/Qwen3-1.7B",
        temperature: float = 0.0,
        *,
        num_beams: int = 8,
        neurologic_lambda: float = DEFAULT_NEUROLOGIC_LAMBDA,
        neurologic_alpha: int = DEFAULT_NEUROLOGIC_ALPHA,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            temperature=temperature,
            num_beams=num_beams,
            **kwargs,
        )
        self._neurologic_lambda = float(neurologic_lambda)
        self._neurologic_alpha = int(neurologic_alpha)

    @property
    def name(self) -> str:
        return "neurologic_hf_thin_plain_b"

    def _beam_generate(
        self,
        *,
        prompt: str,
        system: str,
        expected_form: str,
        morph_ban_set: MorphBanSet | None = None,
    ) -> str:
        return neurologic_generate_one(
            self._model_id,
            system=system,
            user=prompt,
            expected_form=expected_form,
            morph_ban_set=morph_ban_set,
            num_beams=self._num_beams,
            max_new_tokens=self._max_new_tokens_for_mode(),
            neurologic_lambda=self._neurologic_lambda,
            neurologic_alpha=self._neurologic_alpha,
        )

    def generate_many(
        self,
        jobs: list[dict[str, Any]],
        *,
        batch_size: int = 1,
    ) -> list[list[dict[str, str]]]:
        """Sequential per-cell decode (no cross-cell batching in v1)."""
        del batch_size  # unused; Neurologic is single-cell only
        results: list[list[dict[str, str]]] = []
        for job in jobs:
            results.append(
                self.generate(
                    keyword=job["keyword"],
                    translation=job["translation"],
                    constraints=dict(job["constraints"]),
                    num_candidates=int(job["num_candidates"]),
                    target_language=job.get("target_language", "es"),
                    cefr_level=job.get("cefr_level"),
                    sentence_length=job.get("sentence_length", "short"),
                    explicit_subject_required=bool(
                        job.get("explicit_subject_required", False)
                    ),
                )
            )
        return results


class NeurologicHFThinInjectPlainBGenerator(NeurologicHFThinPlainBGenerator):
    """Neurologic thin CNF + gold-form injection + Fix B."""

    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "neurologic_hf_thin_inject_plain_b"

