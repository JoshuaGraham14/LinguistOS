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
)
from research.generation.plain_output import candidate_from_plain
from research.generation.prompt_builder import (
    build_prompt,
    build_prompt_plain,
    language_display_name,
)

DEFAULT_NUM_BEAMS = 4
DEFAULT_BIAS_STRENGTH = 5.0
MAX_NEW_TOKENS_PLAIN = 80
MAX_NEW_TOKENS_JSON = 280


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

        if use_hard_constraint:
            gen_kwargs["force_words_ids"] = [variants for _, _, variants in valid_rows]
            gen_kwargs["custom_generate"] = "transformers-community/constrained-beam-search"
            gen_kwargs["trust_remote_code"] = True
            gen_kwargs["remove_invalid_values"] = True
            if extra_processors:
                gen_kwargs["logits_processor"] = extra_processors
        else:
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

        with torch.no_grad():
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
    ) -> str:
        return beam_generate_batch(
            self._model_id,
            [
                ConstrainedBeamSpec(
                    system=system,
                    user=prompt,
                    expected_form=expected_form,
                    max_new_tokens=self._max_new_tokens_for_mode(),
                )
            ],
            num_beams=self._num_beams,
            use_hard_constraint=self.USE_HARD_CONSTRAINT,
            bias_strength=self._bias_strength,
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
        collected: list[dict[str, str]] = []

        for sample_idx in range(num_candidates):
            scene_hint = None
            if self.SCENE_VARIATION:
                scene_hint = SCENE_HINTS[sample_idx % len(SCENE_HINTS)]

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
            )
            batch, mode = self._parse_raw(raw)
            fired = _form_fired(raw, expected_form)
            print(
                f"    [{self.name} sample {sample_idx + 1}] "
                f"parsed={len(batch)} mode={mode} fired={int(fired)}"
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
        active = list(range(n_jobs))

        for call_idx in range(self.MAX_CALLS):
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
                scene_hint = None
                if self.SCENE_VARIATION:
                    sample_idx = len(collected[idx])
                    scene_hint = SCENE_HINTS[sample_idx % len(SCENE_HINTS)]
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
                bias_strength=self._bias_strength,
                batch_size=batch_size,
                stop_bias_after_hit=self._STOP_BIAS_AFTER_HIT,
                no_repeat_ngram_size=self._no_repeat_ngram_size,
                min_new_tokens=self._min_new_tokens,
                length_penalty=self._length_penalty,
            )

            next_active: list[int] = []
            fired_count = 0
            for job_idx, raw in zip(spec_job_idx, raws):
                batch, mode = self._parse_raw(raw)
                expected = self._job_expected_form(jobs[job_idx]["constraints"])
                fired = _form_fired(raw, expected)
                fired_count += int(fired)
                print(
                    f"    [{self.name} batch call {call_idx + 1} job {job_idx + 1}] "
                    f"parsed={len(batch)} mode={mode} fired={int(fired)}"
                )
                collected[job_idx].extend(batch)
                if (
                    len(collected[job_idx]) < jobs[job_idx]["num_candidates"]
                    and call_idx + 1 < self.MAX_CALLS
                ):
                    next_active.append(job_idx)
            if spec_job_idx:
                print(
                    f"    [{self.name} batch call {call_idx + 1}] "
                    f"firing_rate={fired_count}/{len(spec_job_idx)}"
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
