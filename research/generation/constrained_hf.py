"""Hugging Face constrained decoding for Direction 1 (hard mask + soft bias).

Emits per-cell **constraint firing** telemetry: whether the gold surface form
appears (case-insensitive) somewhere in the decoded sentence. This separates
"constraint fired but wrong syntactic role" from "constraint never fired at
all" — two failure modes with very different implications.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.generation.baseline_hf import (
    BaselineHFGenerator,
    ChatGenerationSpec,
    DEFAULT_HF_BATCH_SIZE,
    _chat_template_text,
    _load_model,
    _strip_thinking,
    parse_candidates_lenient,
    record_cost_telemetry,
)
from research.generation.plain_output import candidate_from_plain
from research.generation.morph_bans import (
    MorphBanSet,
    MorphBanMode,
    banned_surfaces_in_text,
    build_morph_ban_set,
    encode_bad_words,
    encode_surfaces,
)
from research.generation.morph_role import expected_form_is_main_verb
from research.generation.prompt_builder import (
    build_prompt,
    build_prompt_plain,
    language_display_name,
)

DEFAULT_NUM_BEAMS = 4
DEFAULT_BIAS_STRENGTH = 5.0
DEFAULT_MORPH_BAN_PENALTY = 5.0
MAX_NEW_TOKENS_PLAIN = 80
MAX_NEW_TOKENS_JSON = 280
ROLE_RETRY_HINT = (
    "Constraint: use the target verb form as the main finite verb "
    "of the sentence, not as a quote, list item, or side mention."
)


def _form_fired(raw: str, expected_form: str) -> bool:
    """Case-insensitive substring check: did the gold form land in the output?"""
    if not raw or not expected_form:
        return False
    return expected_form.strip().lower() in raw.lower()

SCENE_HINTS: tuple[str, ...] = (
    "Topic: everyday life.",
    "Topic: school or work.",
    "Topic: travel or holidays.",
    "Topic: family and friends.",
    "Topic: food and cooking.",
    "Topic: sports or hobbies.",
    "Topic: shopping.",
    "Topic: health and wellbeing.",
)


@dataclass(frozen=True)
class ConstrainedBeamSpec:
    """One constrained beam request for padded cross-cell batching."""

    system: str
    user: str
    expected_form: str
    max_new_tokens: int
    morph_ban_set: MorphBanSet | None = None
    morph_ban_soft: bool = False
    morph_ban_penalty: float = DEFAULT_MORPH_BAN_PENALTY


def encode_force_variants(tokenizer, form: str) -> list[list[int]]:
    """Token-id sequences for *form* with/without a leading space."""
    variants: list[list[int]] = []
    for prefix in ("", " "):
        ids = tokenizer.encode(prefix + form, add_special_tokens=False)
        if ids and ids not in variants:
            variants.append(ids)
    return variants


def _form_token_ids(tokenizer, form: str) -> set[int]:
    ids: set[int] = set()
    for variant in encode_force_variants(tokenizer, form):
        ids.update(variant)
    return ids


class _FormBiasLogitsProcessor:
    """Add a fixed logit bonus to every token piece in the gold surface form."""

    def __init__(self, token_ids: set[int], bias_strength: float) -> None:
        self._token_ids = token_ids
        self._bias = bias_strength

    def __call__(self, input_ids, scores):
        for tid in self._token_ids:
            if tid < scores.shape[-1]:
                scores[:, tid] = scores[:, tid] + self._bias
        return scores


class _GeneratedOnlyNoRepeatNGramLogitsProcessor:
    """Ban n-gram repeats in the *generated* tail only — not the prompt.

    Hugging Face's built-in ``no_repeat_ngram_size`` also bans n-grams that
    already appear in the prompt. That is lethal for form-injection: the gold
    surface form is named in the prompt, so the model is then forbidden from
    emitting it as the verb. This processor mirrors the same ban logic but
    only inspects tokens past ``prompt_width``.
    """

    def __init__(self, ngram_size: int, prompt_width: int) -> None:
        if ngram_size <= 0:
            raise ValueError(f"ngram_size must be > 0, got {ngram_size}")
        self._ngram_size = int(ngram_size)
        self._prompt_width = int(prompt_width)

    def __call__(self, input_ids, scores):
        import torch

        n = self._ngram_size
        # Clone so we don't mutate a shared scores buffer in-place across
        # processors; HF's own processor does the same.
        scores = scores.clone()
        for idx in range(scores.shape[0]):
            tail = input_ids[idx, self._prompt_width :].tolist()
            if len(tail) < n - 1:
                continue
            seen: dict[tuple[int, ...], set[int]] = {}
            for i in range(len(tail) - n + 1):
                prefix = tuple(tail[i : i + n - 1])
                seen.setdefault(prefix, set()).add(tail[i + n - 1])
            cur_prefix = tuple(tail[-(n - 1) :])
            for tid in seen.get(cur_prefix, ()):
                if tid < scores.shape[-1]:
                    scores[idx, tid] = float("-inf")
        return scores


class _BatchedFormBiasLogitsProcessor:
    """Per-row soft bias for padded beam batches.

    When ``stop_after_hit`` is True, the bias is disabled for a beam once the
    full target token sequence has already appeared in that beam's generated
    tail (past ``prompt_width``). This prevents post-emission repetition loops
    and the "output the form and stop" failure mode.
    """

    def __init__(
        self,
        token_ids_per_row: list[set[int]],
        bias_strength: float,
        num_beams: int,
        variants_per_row: list[list[list[int]]] | None = None,
        prompt_width: int = 0,
        stop_after_hit: bool = False,
    ) -> None:
        self._token_ids_per_row = token_ids_per_row
        self._bias = bias_strength
        self._num_beams = num_beams
        self._variants_per_row = variants_per_row or [[] for _ in token_ids_per_row]
        self._prompt_width = prompt_width
        self._stop_after_hit = stop_after_hit

    @staticmethod
    def _tail_contains_subseq(tail_list: list[int], sub: list[int]) -> bool:
        n = len(sub)
        if n == 0 or len(tail_list) < n:
            return False
        for i in range(len(tail_list) - n + 1):
            if tail_list[i : i + n] == sub:
                return True
        return False

    def _row_already_fired(self, input_ids, idx: int, row: int) -> bool:
        variants = self._variants_per_row[row]
        if not variants:
            return False
        tail = input_ids[idx, self._prompt_width :].tolist()
        if not tail:
            return False
        for variant in variants:
            if self._tail_contains_subseq(tail, list(variant)):
                return True
        return False

    def __call__(self, input_ids, scores):
        for idx in range(scores.shape[0]):
            row = idx // self._num_beams
            if row >= len(self._token_ids_per_row):
                continue
            if self._stop_after_hit and self._row_already_fired(
                input_ids, idx, row
            ):
                continue
            for tid in self._token_ids_per_row[row]:
                if tid < scores.shape[-1]:
                    scores[idx, tid] = scores[idx, tid] + self._bias
        return scores


class _BatchedBadWordsLogitsProcessor:
    """Apply per-input bad-word token sequences across padded beam batches.

    Transformers' native ``bad_words_ids`` is shared by the full batch.  The
    morphology grammar differs for every benchmark cell, so this processor
    applies the appropriate sequence list to each input row and its beams.
    Only generated tokens are inspected; a form named in the prompt does not
    trigger or interfere with the ban.
    """

    def __init__(
        self,
        bad_word_ids_per_row: list[list[list[int]]],
        *,
        num_beams: int,
        prompt_width: int,
    ) -> None:
        self._bad_word_ids_per_row = bad_word_ids_per_row
        self._num_beams = num_beams
        self._prompt_width = prompt_width

    def __call__(self, input_ids, scores):
        scores = scores.clone()
        for idx in range(scores.shape[0]):
            row = idx // self._num_beams
            if row >= len(self._bad_word_ids_per_row):
                continue
            tail = input_ids[idx, self._prompt_width :].tolist()
            for sequence in self._bad_word_ids_per_row[row]:
                if not sequence:
                    continue
                prefix = sequence[:-1]
                if prefix and (
                    len(tail) < len(prefix)
                    or tail[-len(prefix) :] != prefix
                ):
                    continue
                token_id = sequence[-1]
                if token_id < scores.shape[-1]:
                    scores[idx, token_id] = float("-inf")
        return scores


class _BatchedSoftBanLogitsProcessor:
    """Soft-negative morphology bans with optional subject gating.

    Pronoun sequences are always penalised. Competing verb forms are only
    penalised after an allowed subject pronoun has appeared in the generated
    tail (when the ban set requests subject gating). Unlike hard bans, this
    subtracts a finite penalty so soft positive bias can still compete.
    """

    def __init__(
        self,
        always_ids_per_row: list[list[list[int]]],
        gated_ids_per_row: list[list[list[int]]],
        subject_ids_per_row: list[list[list[int]]],
        gate_per_row: list[bool],
        *,
        penalty: float,
        num_beams: int,
        prompt_width: int,
    ) -> None:
        self._always_ids_per_row = always_ids_per_row
        self._gated_ids_per_row = gated_ids_per_row
        self._subject_ids_per_row = subject_ids_per_row
        self._gate_per_row = gate_per_row
        self._penalty = float(penalty)
        self._num_beams = num_beams
        self._prompt_width = prompt_width

    @staticmethod
    def _tail_contains_sequence(tail: list[int], sequence: list[int]) -> bool:
        n = len(sequence)
        if n == 0 or len(tail) < n:
            return False
        for i in range(len(tail) - n + 1):
            if tail[i : i + n] == sequence:
                return True
        return False

    def _subject_seen(self, tail: list[int], row: int) -> bool:
        for sequence in self._subject_ids_per_row[row]:
            if self._tail_contains_sequence(tail, sequence):
                return True
        return False

    def _penalize_sequences(self, scores, idx: int, tail: list[int], sequences):
        for sequence in sequences:
            if not sequence:
                continue
            prefix = sequence[:-1]
            if prefix and (
                len(tail) < len(prefix) or tail[-len(prefix) :] != prefix
            ):
                continue
            token_id = sequence[-1]
            if token_id < scores.shape[-1]:
                scores[idx, token_id] = scores[idx, token_id] - self._penalty

    def __call__(self, input_ids, scores):
        scores = scores.clone()
        for idx in range(scores.shape[0]):
            row = idx // self._num_beams
            if row >= len(self._always_ids_per_row):
                continue
            tail = input_ids[idx, self._prompt_width :].tolist()
            self._penalize_sequences(
                scores, idx, tail, self._always_ids_per_row[row]
            )
            if self._gate_per_row[row] and not self._subject_seen(tail, row):
                continue
            self._penalize_sequences(
                scores, idx, tail, self._gated_ids_per_row[row]
            )
        return scores


def _morph_ban_processors_for_batch(
    tokenizer,
    batch_specs: list[ConstrainedBeamSpec],
    *,
    num_beams: int,
    prompt_width: int,
) -> list[Any]:
    """Build hard or soft morph-ban processors for one padded batch."""
    soft_rows = [
        spec
        for spec in batch_specs
        if spec.morph_ban_set is not None and spec.morph_ban_soft
    ]
    hard_rows = [
        spec
        for spec in batch_specs
        if spec.morph_ban_set is not None and not spec.morph_ban_soft
    ]
    processors: list[Any] = []
    if hard_rows:
        bad_word_ids_per_row = [
            encode_bad_words(tokenizer, spec.morph_ban_set)
            if spec.morph_ban_set is not None and not spec.morph_ban_soft
            else []
            for spec in batch_specs
        ]
        if any(bad_word_ids_per_row):
            processors.append(
                _BatchedBadWordsLogitsProcessor(
                    bad_word_ids_per_row,
                    num_beams=num_beams,
                    prompt_width=prompt_width,
                )
            )
    if soft_rows:
        always_ids_per_row: list[list[list[int]]] = []
        gated_ids_per_row: list[list[list[int]]] = []
        subject_ids_per_row: list[list[list[int]]] = []
        gate_per_row: list[bool] = []
        penalty = DEFAULT_MORPH_BAN_PENALTY
        for spec in batch_specs:
            ban = spec.morph_ban_set
            if ban is None or not spec.morph_ban_soft:
                always_ids_per_row.append([])
                gated_ids_per_row.append([])
                subject_ids_per_row.append([])
                gate_per_row.append(False)
                continue
            penalty = spec.morph_ban_penalty
            if ban.gate_forms_on_subject:
                always_ids_per_row.append(encode_surfaces(tokenizer, ban.pronouns))
                gated_ids_per_row.append(
                    encode_surfaces(tokenizer, ban.competing_forms)
                )
                subject_ids_per_row.append(
                    encode_surfaces(tokenizer, ban.allowed_subjects)
                )
                gate_per_row.append(True)
            else:
                always_ids_per_row.append(encode_bad_words(tokenizer, ban))
                gated_ids_per_row.append([])
                subject_ids_per_row.append([])
                gate_per_row.append(False)
        if any(always_ids_per_row) or any(gated_ids_per_row):
            processors.append(
                _BatchedSoftBanLogitsProcessor(
                    always_ids_per_row,
                    gated_ids_per_row,
                    subject_ids_per_row,
                    gate_per_row,
                    penalty=penalty,
                    num_beams=num_beams,
                    prompt_width=prompt_width,
                )
            )
    return processors


def _beam_generate_batch_once(
    model_id: str,
    specs: list[ConstrainedBeamSpec],
    *,
    num_beams: int,
    use_hard_constraint: bool,
    bias_strength: float,
    stop_bias_after_hit: bool = False,
    no_repeat_ngram_size: int = 0,
    min_new_tokens: int = 0,
    length_penalty: float = 1.0,
) -> list[str]:
    """Run one padded constrained ``model.generate`` call for *specs*."""
    import torch

    if not specs:
        return []

    tokenizer, model = _load_model(model_id)
    prev_padding_side = tokenizer.padding_side
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "left"

    try:
        if use_hard_constraint:
            valid_rows: list[tuple[int, ConstrainedBeamSpec, list[list[int]]]] = []
            for idx, spec in enumerate(specs):
                variants = encode_force_variants(tokenizer, spec.expected_form)
                if variants:
                    valid_rows.append((idx, spec, variants))
            if not valid_rows:
                return [""] * len(specs)
        else:
            valid_rows = [(idx, spec, []) for idx, spec in enumerate(specs)]

        batch_specs = [spec for _, spec, _ in valid_rows]
        texts = [
            _chat_template_text(
                tokenizer,
                model_id,
                ChatGenerationSpec(
                    system=spec.system,
                    user=spec.user,
                    max_new_tokens=spec.max_new_tokens,
                ),
            )
            for spec in batch_specs
        ]
        inputs = tokenizer(texts, return_tensors="pt", padding=True).to(model.device)
        prompt_token_counts = [
            int(v)
            for v in inputs["attention_mask"].sum(dim=1).detach().cpu().tolist()
        ]
        prompt_width = inputs["input_ids"].shape[1]
        max_new_tokens = max(spec.max_new_tokens for spec in batch_specs)
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "num_beams": num_beams,
            "do_sample": False,
            "pad_token_id": tokenizer.pad_token_id,
            "num_return_sequences": 1,
            "length_penalty": length_penalty,
        }
        if min_new_tokens and min_new_tokens > 0:
            gen_kwargs["min_new_tokens"] = min(min_new_tokens, max_new_tokens)

        # Prefer a generated-tail-only n-gram ban over HF's built-in
        # ``no_repeat_ngram_size``, which also bans n-grams from the prompt
        # and therefore blocks form-injection from emitting the gold form.
        extra_processors: list[Any] = []
        if no_repeat_ngram_size and no_repeat_ngram_size > 0:
            extra_processors.append(
                _GeneratedOnlyNoRepeatNGramLogitsProcessor(
                    no_repeat_ngram_size, prompt_width
                )
            )
        extra_processors[0:0] = _morph_ban_processors_for_batch(
            tokenizer,
            batch_specs,
            num_beams=num_beams,
            prompt_width=prompt_width,
        )

        if use_hard_constraint:
            gen_kwargs["force_words_ids"] = [variants for _, _, variants in valid_rows]
            gen_kwargs["custom_generate"] = "transformers-community/constrained-beam-search"
            gen_kwargs["trust_remote_code"] = True
            gen_kwargs["remove_invalid_values"] = True
            if extra_processors:
                gen_kwargs["logits_processor"] = extra_processors
        elif bias_strength > 0:
            variants_per_row = [
                encode_force_variants(tokenizer, spec.expected_form)
                for spec in batch_specs
            ]
            token_ids_per_row = [
                {tid for variant in variants for tid in variant}
                for variants in variants_per_row
            ]
            gen_kwargs["logits_processor"] = [
                _BatchedFormBiasLogitsProcessor(
                    token_ids_per_row,
                    bias_strength,
                    num_beams,
                    variants_per_row=variants_per_row,
                    prompt_width=prompt_width,
                    stop_after_hit=stop_bias_after_hit,
                ),
                *extra_processors,
            ]
        elif extra_processors:
            # Morph-ban-only decoding: deterministic beam search with no
            # positive target bias.
            gen_kwargs["logits_processor"] = extra_processors

        with torch.no_grad():
            record_cost_telemetry(prompt_token_counts)
            output = model.generate(**inputs, **gen_kwargs)

        results = [""] * len(specs)
        for batch_idx, (orig_idx, _, _) in enumerate(valid_rows):
            raw = tokenizer.decode(
                output[batch_idx][prompt_width:],
                skip_special_tokens=True,
            )
            results[orig_idx] = _strip_thinking(raw)
        return results
    finally:
        tokenizer.padding_side = prev_padding_side


def beam_generate_batch(
    model_id: str,
    specs: list[ConstrainedBeamSpec],
    *,
    num_beams: int,
    use_hard_constraint: bool,
    bias_strength: float,
    batch_size: int = DEFAULT_HF_BATCH_SIZE,
    stop_bias_after_hit: bool = False,
    no_repeat_ngram_size: int = 0,
    min_new_tokens: int = 0,
    length_penalty: float = 1.0,
) -> list[str]:
    """Chunk constrained beam specs into padded HF batches."""
    if not specs:
        return []
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    outputs: list[str] = []
    for start in range(0, len(specs), batch_size):
        chunk = specs[start : start + batch_size]
        outputs.extend(
            _beam_generate_batch_once(
                model_id,
                chunk,
                num_beams=num_beams,
                use_hard_constraint=use_hard_constraint,
                bias_strength=bias_strength,
                stop_bias_after_hit=stop_bias_after_hit,
                no_repeat_ngram_size=no_repeat_ngram_size,
                min_new_tokens=min_new_tokens,
                length_penalty=length_penalty,
            )
        )
    return outputs


class ConstrainedHFGenerator(BaselineHFGenerator):
    """Shared beam-search constrained decode for hard and soft variants."""

    USE_HARD_CONSTRAINT = True
    OUTPUT_JSON = False
    SCENE_VARIATION = False
    # Fix A (D1.2 soft-arm ablation): disable soft bias once the target token
    # sequence has appeared in a beam's generated tail. Prevents the
    # "output the form and quit" + post-emission repetition failure modes.
    _STOP_BIAS_AFTER_HIT = False
    # Fix B (D1.2 soft-arm ablation): add an explicit sentence-length +
    # no-bare-form instruction to the prompt.
    _REQUIRE_FULL_SENTENCE = False
    # Diagnostic 4A Spanish morphology overlay (named subject + tense gloss).
    _MORPHOLOGY_HINTS = False
    # Direction 3 is opt-in. Existing Direction 1/1.2 subclasses inherit
    # these inert defaults and keep byte-for-byte equivalent decoding.
    _USE_MORPH_BANS = False
    _MORPH_BAN_MODE: MorphBanMode = "full"
    _USE_SOFT_BIAS = True
    # Direction 3b soft-negative / subject-gated refinements (opt-in).
    _MORPH_BAN_SOFT = False
    _MORPH_BAN_PENALTY = DEFAULT_MORPH_BAN_PENALTY
    _MORPH_BAN_SUBJECT_GATE = False
    _ROLE_RESAMPLE = False
    _ROLE_RESAMPLE_MAX = 3

    def _system_prompt(self, lang: str) -> str:
        if self.OUTPUT_JSON:
            return (
                f"You are a helpful {lang} language tutor. "
                "Always respond with valid JSON."
            )
        return (
            f"You are a helpful {lang} language tutor. "
            "Reply with exactly one Spanish sentence per request."
        )

    def _max_new_tokens_for_mode(self) -> int:
        return MAX_NEW_TOKENS_JSON if self.OUTPUT_JSON else MAX_NEW_TOKENS_PLAIN

    def _build_user_prompt(
        self,
        *,
        keyword: str,
        translation: str,
        target_language: str,
        constraints: dict[str, Any],
        num_candidates: int,
        sentence_length: str,
        cefr_level: str | None,
        explicit_subject_required: bool,
        inject_expected_form: str | None,
        scene_hint: str | None = None,
    ) -> str:
        if self.OUTPUT_JSON:
            return build_prompt(
                keyword=keyword,
                translation=translation,
                target_language=target_language,
                constraints=constraints,
                num_candidates=num_candidates,
                sentence_length=sentence_length,
                cefr_level=cefr_level,
                explicit_subject_required=explicit_subject_required,
                inject_expected_form=inject_expected_form,
            )
        return build_prompt_plain(
            keyword=keyword,
            translation=translation,
            target_language=target_language,
            constraints=constraints,
            num_candidates=num_candidates,
            sentence_length=sentence_length,
            cefr_level=cefr_level,
            explicit_subject_required=explicit_subject_required,
            inject_expected_form=inject_expected_form,
            scene_hint=scene_hint,
            require_full_sentence=self._REQUIRE_FULL_SENTENCE,
            morphology_hints=self._MORPHOLOGY_HINTS,
        )

    def _beam_generate(
        self,
        *,
        prompt: str,
        system: str,
        expected_form: str,
        morph_ban_set: MorphBanSet | None = None,
    ) -> str:
        return beam_generate_batch(
            self._model_id,
            [
                ConstrainedBeamSpec(
                    system=system,
                    user=prompt,
                    expected_form=expected_form,
                    max_new_tokens=self._max_new_tokens_for_mode(),
                    morph_ban_set=morph_ban_set,
                    morph_ban_soft=self._MORPH_BAN_SOFT,
                    morph_ban_penalty=self._MORPH_BAN_PENALTY,
                )
            ],
            num_beams=self._num_beams,
            use_hard_constraint=self.USE_HARD_CONSTRAINT,
            bias_strength=self._bias_strength if self._USE_SOFT_BIAS else 0.0,
            batch_size=1,
            stop_bias_after_hit=self._STOP_BIAS_AFTER_HIT,
            no_repeat_ngram_size=self._no_repeat_ngram_size,
            min_new_tokens=self._min_new_tokens,
            length_penalty=self._length_penalty,
        )[0]

    def _parse_raw(self, raw: str) -> tuple[list[dict[str, str]], str]:
        if self.OUTPUT_JSON:
            cands, mode = parse_candidates_lenient(raw)
            return cands, mode
        cand, mode = candidate_from_plain(raw)
        if cand["sentence"]:
            return [cand], mode
        return [], mode

    def _job_expected_form(self, constraints: dict[str, Any]) -> str:
        return (constraints.get("expected_form") or "").strip()

    def _job_morph_ban_set(
        self,
        keyword: str,
        constraints: dict[str, Any],
    ) -> MorphBanSet | None:
        if not self._USE_MORPH_BANS:
            return None
        return build_morph_ban_set(
            keyword,
            str(constraints.get("tense") or ""),
            str(constraints.get("person") or ""),
            str(constraints.get("number") or ""),
            self._job_expected_form(constraints),
            mode=self._MORPH_BAN_MODE,
            gate_forms_on_subject=self._MORPH_BAN_SUBJECT_GATE,
        )

    def _role_ok(self, sentence: str, expected_form: str) -> bool:
        if not self._ROLE_RESAMPLE:
            return True
        return expected_form_is_main_verb(sentence, expected_form)

    def _scene_hint_for_attempt(
        self,
        attempt_idx: int,
        *,
        constraints: dict[str, Any] | None = None,
    ) -> str | None:
        del constraints  # base class ignores cell metadata
        if self.SCENE_VARIATION:
            return SCENE_HINTS[attempt_idx % len(SCENE_HINTS)]
        if self._ROLE_RESAMPLE and attempt_idx > 0:
            # Deterministic beam needs a prompt change to explore alternatives.
            if attempt_idx == 1:
                return ROLE_RETRY_HINT
            return SCENE_HINTS[(attempt_idx - 1) % len(SCENE_HINTS)]
        return None

    def generate(
        self,
        keyword: str,
        translation: str,
        constraints: dict[str, Any],
        num_candidates: int,
        *,
        target_language: str = "es",
        cefr_level: str | None = None,
        sentence_length: str = "short",
        explicit_subject_required: bool = False,
    ) -> list[dict[str, str]]:
        expected_form = self._job_expected_form(constraints)
        if not expected_form:
            print(f"    [{self.name}] missing expected_form — skipping")
            return []

        lang = language_display_name(target_language)
        system = self._system_prompt(lang)
        morph_ban_set = self._job_morph_ban_set(keyword, constraints)
        collected: list[dict[str, str]] = []
        max_attempts = (
            max(num_candidates, self._ROLE_RESAMPLE_MAX)
            if self._ROLE_RESAMPLE
            else num_candidates
        )

        for sample_idx in range(max_attempts):
            scene_hint = self._scene_hint_for_attempt(
                sample_idx, constraints=constraints
            )

            prompt = self._build_user_prompt(
                keyword=keyword,
                translation=translation,
                target_language=target_language,
                constraints=constraints,
                num_candidates=1,
                sentence_length=sentence_length,
                cefr_level=cefr_level,
                explicit_subject_required=explicit_subject_required,
                inject_expected_form=self._resolve_inject_expected_form(constraints),
                scene_hint=scene_hint,
            )
            raw = self._beam_generate(
                prompt=prompt,
                system=system,
                expected_form=expected_form,
                morph_ban_set=morph_ban_set,
            )
            batch, mode = self._parse_raw(raw)
            fired = _form_fired(raw, expected_form)
            banned_hits = (
                banned_surfaces_in_text(raw, morph_ban_set)
                if morph_ban_set is not None
                else frozenset()
            )
            role_ok = True
            if batch and self._ROLE_RESAMPLE:
                role_ok = self._role_ok(batch[0].get("sentence", ""), expected_form)
                if not role_ok and sample_idx + 1 < max_attempts:
                    print(
                        f"    [{self.name} sample {sample_idx + 1}] "
                        f"role_reject retrying mode={mode} fired={int(fired)}"
                    )
                    continue
            morph_telemetry = (
                f" banned_hit={int(bool(banned_hits))}"
                f" ban_count={len(morph_ban_set.surfaces)}"
                f" ban_mode={morph_ban_set.mode}"
                f" soft_ban={int(self._MORPH_BAN_SOFT)}"
                if morph_ban_set is not None
                else ""
            )
            role_telemetry = (
                f" role_ok={int(role_ok)}" if self._ROLE_RESAMPLE else ""
            )
            print(
                f"    [{self.name} sample {sample_idx + 1}] "
                f"parsed={len(batch)} mode={mode} fired={int(fired)}"
                f"{morph_telemetry}{role_telemetry}"
            )
            collected.extend(batch)
            if len(collected) >= num_candidates:
                break

        return collected[:num_candidates]

    def generate_many(
        self,
        jobs: list[dict[str, Any]],
        *,
        batch_size: int = DEFAULT_HF_BATCH_SIZE,
    ) -> list[list[dict[str, str]]]:
        """Generate constrained beam outputs for multiple constraint-set jobs."""
        if not jobs:
            return []

        n_jobs = len(jobs)
        collected: list[list[dict[str, str]]] = [[] for _ in range(n_jobs)]
        role_attempts: list[int] = [0] * n_jobs
        active = list(range(n_jobs))
        max_calls = self.MAX_CALLS
        if self._ROLE_RESAMPLE:
            max_calls = max(max_calls, self._ROLE_RESAMPLE_MAX)

        for call_idx in range(max_calls):
            if not active:
                break

            specs: list[ConstrainedBeamSpec] = []
            spec_job_idx: list[int] = []
            for idx in active:
                job = jobs[idx]
                remaining = job["num_candidates"] - len(collected[idx])
                if remaining <= 0:
                    continue
                constraints = dict(job["constraints"])
                expected_form = self._job_expected_form(constraints)
                if not expected_form:
                    continue
                lang = language_display_name(job.get("target_language", "es"))
                attempt_idx = (
                    role_attempts[idx]
                    if self._ROLE_RESAMPLE
                    else len(collected[idx])
                )
                scene_hint = self._scene_hint_for_attempt(
                    attempt_idx, constraints=constraints
                )
                prompt = self._build_user_prompt(
                    keyword=job["keyword"],
                    translation=job["translation"],
                    target_language=job.get("target_language", "es"),
                    constraints=constraints,
                    num_candidates=1,
                    sentence_length=job.get("sentence_length", "short"),
                    cefr_level=job.get("cefr_level"),
                    explicit_subject_required=bool(
                        job.get("explicit_subject_required", False)
                    ),
                    inject_expected_form=self._resolve_inject_expected_form(constraints),
                    scene_hint=scene_hint,
                )
                specs.append(
                    ConstrainedBeamSpec(
                        system=self._system_prompt(lang),
                        user=prompt,
                        expected_form=expected_form,
                        max_new_tokens=self._max_new_tokens_for_mode(),
                        morph_ban_set=self._job_morph_ban_set(
                            str(job["keyword"]),
                            constraints,
                        ),
                        morph_ban_soft=self._MORPH_BAN_SOFT,
                        morph_ban_penalty=self._MORPH_BAN_PENALTY,
                    )
                )
                spec_job_idx.append(idx)

            if not specs:
                break

            raws = beam_generate_batch(
                self._model_id,
                specs,
                num_beams=self._num_beams,
                use_hard_constraint=self.USE_HARD_CONSTRAINT,
                bias_strength=self._bias_strength if self._USE_SOFT_BIAS else 0.0,
                batch_size=batch_size,
                stop_bias_after_hit=self._STOP_BIAS_AFTER_HIT,
                no_repeat_ngram_size=self._no_repeat_ngram_size,
                min_new_tokens=self._min_new_tokens,
                length_penalty=self._length_penalty,
            )

            next_active: list[int] = []
            fired_count = 0
            banned_hit_count = 0
            role_reject_count = 0
            for job_idx, spec, raw in zip(spec_job_idx, specs, raws):
                batch, mode = self._parse_raw(raw)
                expected = self._job_expected_form(jobs[job_idx]["constraints"])
                fired = _form_fired(raw, expected)
                fired_count += int(fired)
                banned_hits = (
                    banned_surfaces_in_text(raw, spec.morph_ban_set)
                    if spec.morph_ban_set is not None
                    else frozenset()
                )
                banned_hit_count += int(bool(banned_hits))
                role_ok = True
                if batch and self._ROLE_RESAMPLE:
                    role_ok = self._role_ok(
                        batch[0].get("sentence", ""), expected
                    )
                    if not role_ok:
                        role_attempts[job_idx] += 1
                        role_reject_count += 1
                        if (
                            role_attempts[job_idx] < self._ROLE_RESAMPLE_MAX
                            and call_idx + 1 < max_calls
                        ):
                            print(
                                f"    [{self.name} batch call {call_idx + 1} "
                                f"job {job_idx + 1}] role_reject retrying "
                                f"attempt={role_attempts[job_idx]}"
                            )
                            next_active.append(job_idx)
                            continue
                morph_telemetry = (
                    f" banned_hit={int(bool(banned_hits))}"
                    f" ban_count={len(spec.morph_ban_set.surfaces)}"
                    f" ban_mode={spec.morph_ban_set.mode}"
                    f" soft_ban={int(spec.morph_ban_soft)}"
                    if spec.morph_ban_set is not None
                    else ""
                )
                role_telemetry = (
                    f" role_ok={int(role_ok)}" if self._ROLE_RESAMPLE else ""
                )
                print(
                    f"    [{self.name} batch call {call_idx + 1} job {job_idx + 1}] "
                    f"parsed={len(batch)} mode={mode} fired={int(fired)}"
                    f"{morph_telemetry}{role_telemetry}"
                )
                collected[job_idx].extend(batch)
                if (
                    len(collected[job_idx]) < jobs[job_idx]["num_candidates"]
                    and call_idx + 1 < max_calls
                ):
                    next_active.append(job_idx)
            if spec_job_idx:
                morph_summary = (
                    f" banned_hit_rate={banned_hit_count}/{len(spec_job_idx)}"
                    if self._USE_MORPH_BANS
                    else ""
                )
                role_summary = (
                    f" role_rejects={role_reject_count}/{len(spec_job_idx)}"
                    if self._ROLE_RESAMPLE
                    else ""
                )
                print(
                    f"    [{self.name} batch call {call_idx + 1}] "
                    f"firing_rate={fired_count}/{len(spec_job_idx)}"
                    f"{morph_summary}{role_summary}"
                )
            active = next_active

        return [
            collected[i][: jobs[i]["num_candidates"]]
            for i in range(n_jobs)
        ]


class ConstrainedHFHardPlainGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = True
    OUTPUT_JSON = False

    @property
    def name(self) -> str:
        return "constrained_hf_hard_plain"


class ConstrainedHFHardJsonGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = True
    OUTPUT_JSON = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_json"


class ConstrainedHFHardInjectPlainGenerator(ConstrainedHFGenerator):
    """Hard beam constraint **plus** gold form injected in prompt (D1.2 combo arm).

    Isolates: does explicit prompt guidance help beam+force at all, or is the
    decode-time constraint already saturating what greedy would do with the
    prompt-level cue?
    """

    USE_HARD_CONSTRAINT = True
    OUTPUT_JSON = False
    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_inject_plain"


class ConstrainedHFHardPlainBGenerator(ConstrainedHFHardPlainGenerator):
    """Hard beam + Fix B sentence prompt (no gold-form injection)."""

    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_plain_b"


class ConstrainedHFHardInjectPlainBGenerator(ConstrainedHFHardInjectPlainGenerator):
    """Hard beam + form injection + Fix B sentence prompt."""

    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_inject_plain_b"


class ConstrainedHFSoftPlainGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = False

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain"


class ConstrainedHFSoftInjectPlainGenerator(ConstrainedHFGenerator):
    """Soft logit bias **plus** gold form injected in prompt (D1.2 combo arm).

    Hypothesis: pure soft (48%) misses on low-frequency morphological slots
    (2nd person forms) because a fixed logit bonus can't overcome the model's
    weak prior for them. Adding the gold form to the prompt gives the model
    an explicit target while the soft bias reinforces those tokens at decode
    time — without the presence-obligation that made hard collapse into
    conjugation dumps. Expected to sit between soft and inject on form-match
    while preserving natural-sentence output.
    """

    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = False
    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_inject_plain"


class ConstrainedHFSoftJsonGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_json"


# --- D1.2 Fix A / Fix B ablation grid ---------------------------------------
# All six variants below share the same base recipe as their non-suffixed
# parent; only the two class attributes flip. See _STOP_BIAS_AFTER_HIT and
# _REQUIRE_FULL_SENTENCE on ConstrainedHFGenerator for what each does.


class ConstrainedHFSoftPlainAGenerator(ConstrainedHFSoftPlainGenerator):
    _STOP_BIAS_AFTER_HIT = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain_a"


class ConstrainedHFSoftPlainBGenerator(ConstrainedHFSoftPlainGenerator):
    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain_b"


class ConstrainedHFSoftPlainBExplicitGenerator(ConstrainedHFSoftPlainBGenerator):
    """Soft Fix B plus Diagnostic 4A Spanish morphology overlay."""

    _MORPHOLOGY_HINTS = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain_b_explicit"


class ConstrainedHFSoftPlainABGenerator(ConstrainedHFSoftPlainGenerator):
    _STOP_BIAS_AFTER_HIT = True
    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain_ab"


class ConstrainedHFSoftInjectPlainAGenerator(ConstrainedHFSoftInjectPlainGenerator):
    _STOP_BIAS_AFTER_HIT = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_inject_plain_a"


class ConstrainedHFSoftInjectPlainBGenerator(ConstrainedHFSoftInjectPlainGenerator):
    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_inject_plain_b"


class ConstrainedHFSoftInjectPlainABGenerator(ConstrainedHFSoftInjectPlainGenerator):
    _STOP_BIAS_AFTER_HIT = True
    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_inject_plain_ab"


class ConstrainedHFSoftDiversePlainGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = False
    SCENE_VARIATION = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_diverse_plain"


# --- Direction 3 morphology-aware negative grammar --------------------------
# All variants are additive subclasses. Direction 1/1.2 classes above retain
# _USE_MORPH_BANS=False and are unaffected.


class ConstrainedHFMorphBanPlainBGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    _USE_SOFT_BIAS = False
    _USE_MORPH_BANS = True
    _REQUIRE_FULL_SENTENCE = True

    @property
    def name(self) -> str:
        return "constrained_hf_morph_ban_plain_b"


class ConstrainedHFMorphBanInjectPlainBGenerator(
    ConstrainedHFMorphBanPlainBGenerator
):
    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "constrained_hf_morph_ban_inject_plain_b"


class ConstrainedHFHardMorphPlainBGenerator(ConstrainedHFHardPlainBGenerator):
    _USE_MORPH_BANS = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_morph_plain_b"


class ConstrainedHFHardMorphInjectPlainBGenerator(
    ConstrainedHFHardInjectPlainBGenerator
):
    _USE_MORPH_BANS = True

    @property
    def name(self) -> str:
        return "constrained_hf_hard_morph_inject_plain_b"


class ConstrainedHFSoftMorphPlainBGenerator(ConstrainedHFSoftPlainBGenerator):
    _USE_MORPH_BANS = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_plain_b"


class ConstrainedHFSoftMorphInjectPlainBGenerator(
    ConstrainedHFSoftInjectPlainBGenerator
):
    _USE_MORPH_BANS = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_inject_plain_b"


class ConstrainedHFSoftMorphFormsPlainBGenerator(
    ConstrainedHFSoftMorphPlainBGenerator
):
    _MORPH_BAN_MODE: MorphBanMode = "forms_only"

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_forms_plain_b"


class ConstrainedHFSoftMorphPronPlainBGenerator(
    ConstrainedHFSoftMorphPlainBGenerator
):
    _MORPH_BAN_MODE: MorphBanMode = "pronouns_only"

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_pron_plain_b"


# --- Direction 3b soft-negative thin + subject-gated refinements -------------


class ConstrainedHFSoftMorphSoftnegThinPlainBGenerator(
    ConstrainedHFSoftPlainBGenerator
):
    """Soft λ=5 + soft-negative thin bans with subject gating."""

    _USE_MORPH_BANS = True
    _MORPH_BAN_MODE: MorphBanMode = "thin"
    _MORPH_BAN_SOFT = True
    _MORPH_BAN_SUBJECT_GATE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_softneg_thin_plain_b"


class ConstrainedHFSoftMorphSoftnegThinInjectPlainBGenerator(
    ConstrainedHFSoftInjectPlainBGenerator
):
    """Soft λ=5 + inject + soft-negative thin bans with subject gating."""

    _USE_MORPH_BANS = True
    _MORPH_BAN_MODE: MorphBanMode = "thin"
    _MORPH_BAN_SOFT = True
    _MORPH_BAN_SUBJECT_GATE = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_softneg_thin_inject_plain_b"


class ConstrainedHFSoftMorphSoftnegThinInjectRolePlainBGenerator(
    ConstrainedHFSoftMorphSoftnegThinInjectPlainBGenerator
):
    """Soft + inject + softneg thin + local main-verb role resample."""

    _ROLE_RESAMPLE = True
    _ROLE_RESAMPLE_MAX = 3

    @property
    def name(self) -> str:
        return "constrained_hf_soft_morph_softneg_thin_inject_role_plain_b"
