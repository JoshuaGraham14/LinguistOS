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


class _BatchedFormBiasLogitsProcessor:
    """Per-row soft bias for padded beam batches."""

    def __init__(
        self,
        token_ids_per_row: list[set[int]],
        bias_strength: float,
        num_beams: int,
    ) -> None:
        self._token_ids_per_row = token_ids_per_row
        self._bias = bias_strength
        self._num_beams = num_beams

    def __call__(self, input_ids, scores):
        for idx in range(scores.shape[0]):
            row = idx // self._num_beams
            if row >= len(self._token_ids_per_row):
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
        max_new_tokens = max(spec.max_new_tokens for spec in batch_specs)
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "num_beams": num_beams,
            "do_sample": False,
            "pad_token_id": tokenizer.pad_token_id,
            "num_return_sequences": 1,
        }

        if use_hard_constraint:
            gen_kwargs["force_words_ids"] = [variants for _, _, variants in valid_rows]
            gen_kwargs["custom_generate"] = "transformers-community/constrained-beam-search"
            gen_kwargs["trust_remote_code"] = True
            gen_kwargs["remove_invalid_values"] = True
        else:
            token_ids_per_row = [
                _form_token_ids(tokenizer, spec.expected_form) for spec in batch_specs
            ]
            gen_kwargs["logits_processor"] = [
                _BatchedFormBiasLogitsProcessor(
                    token_ids_per_row,
                    bias_strength,
                    num_beams,
                )
            ]

        with torch.no_grad():
            output = model.generate(**inputs, **gen_kwargs)

        prompt_width = inputs["input_ids"].shape[1]
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
            )
        )
    return outputs


class ConstrainedHFGenerator(BaselineHFGenerator):
    """Shared beam-search constrained decode for hard and soft variants."""

    USE_HARD_CONSTRAINT = True
    OUTPUT_JSON = False
    SCENE_VARIATION = False

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


class ConstrainedHFSoftPlainGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = False

    @property
    def name(self) -> str:
        return "constrained_hf_soft_plain"


class ConstrainedHFSoftJsonGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_json"


class ConstrainedHFSoftDiversePlainGenerator(ConstrainedHFGenerator):
    USE_HARD_CONSTRAINT = False
    OUTPUT_JSON = False
    SCENE_VARIATION = True

    @property
    def name(self) -> str:
        return "constrained_hf_soft_diverse_plain"
