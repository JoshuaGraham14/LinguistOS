"""Baseline Hugging Face generation -- batched, local small models.

Mirrors ``baseline_gpt`` (same prompt, same batched request for N candidates)
but runs a local transformers chat model instead of the OpenAI API.

Small models frequently emit malformed JSON, so parsing is lenient:
strict JSON first, then first-{...}-block extraction, then a regex scrape of
"sentence"/"translation" pairs. If a call yields fewer than the requested
number of candidates, additional top-up calls are made (capped) so each case
still receives ~N sentences to evaluate. Per-call parse outcomes are printed
so degradation is visible in the run log.

Multi-prompt cluster batching (several constraint sets per ``model.generate``)
lives in :func:`generate_chat_batch` and pipeline integration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from research.generation.base import BaseGenerator
from research.generation.prompt_builder import (
    build_prompt,
    build_prompt_explicit,
    build_prompt_plain,
    language_display_name,
)

# One model per process; cached across constraint sets.
_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}

_PAIR_RE = re.compile(
    r'"sentence"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"translation"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.DOTALL,
)
_THINKING_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _is_qwen3(model_id: str) -> bool:
    return "qwen3" in model_id.lower()


def _strip_thinking(raw: str) -> str:
    cleaned = _THINKING_RE.sub("", raw)
    for token in ('<|im_end|>', '<|endoftext|>', '<|im_start|>'):
        cleaned = cleaned.replace(token, "")
    return cleaned.strip()


def unload_model(model_id: str) -> None:
    """Drop a cached model so the next checkpoint can load without OOM."""
    cached = _MODEL_CACHE.pop(model_id, None)
    if cached is None:
        return
    import gc

    import torch

    _, model = cached
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _load_model(model_id: str) -> tuple[Any, Any]:
    if model_id in _MODEL_CACHE:
        return _MODEL_CACHE[model_id]

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    # eager attention: MPS sdpa kernel fails on grouped-query attention shapes.
    use_fp16 = device in ("mps", "cuda")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.float16 if use_fp16 else torch.float32,
        attn_implementation="eager",
    )
    model.to(device)
    model.eval()
    _MODEL_CACHE[model_id] = (tokenizer, model)
    return tokenizer, model


def _unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except json.JSONDecodeError:
        return s


def parse_candidates_lenient(raw: str) -> tuple[list[dict[str, str]], str]:
    """Parse model output into candidates; returns (candidates, parse_mode).

    parse_mode is one of: json, json_block, regex, failed.
    """
    def _from_obj(data: Any) -> list[dict[str, str]]:
        items = data.get("candidates", []) if isinstance(data, dict) else []
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            sentence = str(item.get("sentence", "")).strip()
            translation = str(item.get("translation", "")).strip()
            if sentence and translation:
                out.append({"sentence": sentence, "translation": translation})
        return out

    try:
        cands = _from_obj(json.loads(raw))
        if cands:
            return cands, "json"
    except json.JSONDecodeError:
        pass

    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            cands = _from_obj(json.loads(raw[start : end + 1]))
            if cands:
                return cands, "json_block"
        except json.JSONDecodeError:
            pass

    pairs = [
        {"sentence": _unescape(s).strip(), "translation": _unescape(t).strip()}
        for s, t in _PAIR_RE.findall(raw)
    ]
    pairs = [p for p in pairs if p["sentence"] and p["translation"]]
    if pairs:
        return pairs, "regex"

    return [], "failed"


def _sample_kwargs(temperature: float) -> dict[str, Any]:
    """Greedy decode at T=0; stochastic sampling above zero."""
    if temperature <= 0:
        return {"do_sample": False}
    return {"do_sample": True, "temperature": temperature, "top_p": 0.9}


DEFAULT_HF_BATCH_SIZE = 8


@dataclass(frozen=True)
class ChatGenerationSpec:
    """One chat completion request for local HF generation."""

    system: str
    user: str
    max_new_tokens: int


def _chat_template_text(tokenizer: Any, model_id: str, spec: ChatGenerationSpec) -> str:
    messages = [
        {"role": "system", "content": spec.system},
        {"role": "user", "content": spec.user},
    ]
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": True,
        "tokenize": False,
    }
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    return tokenizer.apply_chat_template(messages, **template_kwargs)


def _generate_chat_batch_once(
    model_id: str,
    specs: list[ChatGenerationSpec],
    *,
    temperature: float,
) -> list[str]:
    """Run one padded ``model.generate`` call for *specs* (must be non-empty)."""
    import torch

    tokenizer, model = _load_model(model_id)
    prev_padding_side = tokenizer.padding_side
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    tokenizer.padding_side = "left"

    try:
        texts = [_chat_template_text(tokenizer, model_id, spec) for spec in specs]
        inputs = tokenizer(texts, return_tensors="pt", padding=True).to(model.device)
        max_new_tokens = max(spec.max_new_tokens for spec in specs)
        gen_kwargs = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": tokenizer.pad_token_id,
            **_sample_kwargs(temperature),
        }
        with torch.no_grad():
            output = model.generate(**inputs, **gen_kwargs)

        prompt_width = inputs["input_ids"].shape[1]
        results: list[str] = []
        for idx in range(len(specs)):
            raw = tokenizer.decode(
                output[idx][prompt_width:],
                skip_special_tokens=True,
            )
            results.append(_strip_thinking(raw))
        return results
    finally:
        tokenizer.padding_side = prev_padding_side


def generate_chat(
    model_id: str,
    spec: ChatGenerationSpec,
    *,
    temperature: float = 0.0,
) -> str:
    """Single chat completion via the shared HF path."""
    return generate_chat_batch(model_id, [spec], temperature=temperature)[0]


def generate_chat_batch(
    model_id: str,
    specs: list[ChatGenerationSpec],
    *,
    temperature: float = 0.0,
    batch_size: int = DEFAULT_HF_BATCH_SIZE,
) -> list[str]:
    """Generate chat completions, chunking into padded HF batches."""
    if not specs:
        return []
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    outputs: list[str] = []
    for start in range(0, len(specs), batch_size):
        chunk = specs[start : start + batch_size]
        outputs.extend(
            _generate_chat_batch_once(model_id, chunk, temperature=temperature)
        )
    return outputs


class BaselineHFGenerator(BaseGenerator):
    """Batched generation with a local Hugging Face chat model."""

    # One batched call like baseline_gpt, plus top-up calls if short.
    MAX_CALLS = 4

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-0.5B-Instruct",
        temperature: float = 0.7,
        *,
        num_beams: int = 4,
        bias_strength: float = 5.0,
    ):
        self._model_id = model
        self._temperature = temperature
        self._num_beams = num_beams
        self._bias_strength = bias_strength

    @property
    def name(self) -> str:
        return "baseline_hf"

    def _call(self, prompt: str, system: str, max_new_tokens: int) -> str:
        return generate_chat(
            self._model_id,
            ChatGenerationSpec(system=system, user=prompt, max_new_tokens=max_new_tokens),
            temperature=self._temperature,
        )

    # Subclasses can override to inject the gold ``expected_form`` into the
    # prompt; ``None`` keeps the prompt byte-identical to the baseline.
    _INJECT_EXPECTED_FORM: bool = False

    def _resolve_inject_expected_form(self, constraints: dict[str, Any]) -> str | None:
        if not self._INJECT_EXPECTED_FORM:
            return None
        expected = constraints.get("expected_form")
        return str(expected) if expected else None

    def _json_system_prompt(self, lang: str) -> str:
        return (
            f"You are a helpful {lang} language tutor. "
            "Always respond with valid JSON."
        )

    def _generation_system_prompt(self, lang: str) -> str:
        return self._json_system_prompt(lang)

    def _parse_generation_raw(self, raw: str) -> tuple[list[dict[str, str]], str]:
        return parse_candidates_lenient(raw)

    def _max_new_tokens_for_remaining(self, remaining: int) -> int:
        return self._max_new_tokens(remaining)

    def _max_candidates_per_call(self) -> int:
        return 10_000

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
    ) -> str:
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

    def _max_new_tokens(self, num_candidates: int) -> int:
        return min(80 * num_candidates + 200, 3072)

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
        lang = language_display_name(target_language)
        system = self._generation_system_prompt(lang)
        inject_expected_form = self._resolve_inject_expected_form(constraints)

        collected: list[dict[str, str]] = []
        for call_idx in range(self.MAX_CALLS):
            remaining = num_candidates - len(collected)
            if remaining <= 0:
                break
            prompt = self._build_user_prompt(
                keyword=keyword,
                translation=translation,
                target_language=target_language,
                constraints=constraints,
                num_candidates=remaining,
                sentence_length=sentence_length,
                cefr_level=cefr_level,
                explicit_subject_required=explicit_subject_required,
                inject_expected_form=inject_expected_form,
            )
            raw = self._call(
                prompt,
                system,
                self._max_new_tokens_for_remaining(remaining),
            )
            cands, mode = self._parse_generation_raw(raw)
            print(
                f"    [{self.name} call {call_idx + 1}] requested={remaining} "
                f"parsed={len(cands)} mode={mode}"
            )
            collected.extend(cands[: self._max_candidates_per_call()])

        return collected[:num_candidates]

    def generate_many(
        self,
        jobs: list[dict[str, Any]],
        *,
        batch_size: int = DEFAULT_HF_BATCH_SIZE,
    ) -> list[list[dict[str, str]]]:
        """Generate for multiple constraint-set jobs with padded HF batching.

        Each job dict must include: keyword, translation, constraints,
        num_candidates, target_language, sentence_length, cefr_level,
        explicit_subject_required.
        """
        if not jobs:
            return []

        n_jobs = len(jobs)
        collected: list[list[dict[str, str]]] = [[] for _ in range(n_jobs)]
        active = list(range(n_jobs))

        for call_idx in range(self.MAX_CALLS):
            if not active:
                break
            specs: list[ChatGenerationSpec] = []
            for idx in active:
                job = jobs[idx]
                remaining = job["num_candidates"] - len(collected[idx])
                if remaining <= 0:
                    continue
                constraints = dict(job["constraints"])
                inject = self._resolve_inject_expected_form(constraints)
                lang = language_display_name(job.get("target_language", "es"))
                prompt = self._build_user_prompt(
                    keyword=job["keyword"],
                    translation=job["translation"],
                    target_language=job.get("target_language", "es"),
                    constraints=constraints,
                    num_candidates=remaining,
                    sentence_length=job.get("sentence_length", "short"),
                    cefr_level=job.get("cefr_level"),
                    explicit_subject_required=bool(
                        job.get("explicit_subject_required", False)
                    ),
                    inject_expected_form=inject,
                )
                specs.append(
                    ChatGenerationSpec(
                        system=self._generation_system_prompt(lang),
                        user=prompt,
                        max_new_tokens=self._max_new_tokens_for_remaining(remaining),
                    )
                )

            if not specs:
                break

            raws = generate_chat_batch(
                self._model_id,
                specs,
                temperature=self._temperature,
                batch_size=batch_size,
            )

            next_active: list[int] = []
            spec_i = 0
            for idx in active:
                remaining = jobs[idx]["num_candidates"] - len(collected[idx])
                if remaining <= 0:
                    continue
                raw = raws[spec_i]
                spec_i += 1
                cands, mode = self._parse_generation_raw(raw)
                print(
                    f"    [{self.name} batch call {call_idx + 1} job {idx + 1}] "
                    f"requested={remaining} parsed={len(cands)} mode={mode}"
                )
                collected[idx].extend(cands[: self._max_candidates_per_call()])
                if (
                    len(collected[idx]) < jobs[idx]["num_candidates"]
                    and call_idx + 1 < self.MAX_CALLS
                ):
                    next_active.append(idx)
            active = next_active

        return [
            collected[i][: jobs[i]["num_candidates"]]
            for i in range(n_jobs)
        ]


class FormInjectedHFGenerator(BaselineHFGenerator):
    """``baseline_hf`` with the gold ``expected_form`` injected into the prompt."""

    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "baseline_hf_form_injected"


class FormInjectedExplicitHFGenerator(FormInjectedHFGenerator):
    """Form injection plus the Spanish ``build_prompt_explicit`` overlay (Diag 5C)."""

    @property
    def name(self) -> str:
        return "baseline_hf_form_injected_explicit"

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
    ) -> str:
        return build_prompt_explicit(
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


class PlainHFGenerator(BaselineHFGenerator):
    """``baseline_hf`` with plain-text output (no JSON scaffold)."""

    @property
    def name(self) -> str:
        return "baseline_hf_plain"

    def _generation_system_prompt(self, lang: str) -> str:
        return (
            f"You are a helpful {lang} language tutor. "
            "Reply with exactly one Spanish sentence per request."
        )

    def _parse_generation_raw(self, raw: str) -> tuple[list[dict[str, str]], str]:
        from research.generation.plain_output import candidate_from_plain

        cand, mode = candidate_from_plain(raw)
        if cand["sentence"]:
            return [cand], mode
        return [], mode

    def _max_new_tokens_for_remaining(self, remaining: int) -> int:
        return min(40 * remaining + 40, 512)

    def _max_candidates_per_call(self) -> int:
        return 1

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


class FormInjectedPlainHFGenerator(PlainHFGenerator):
    """Form injection with plain-text output and greedy/stochastic HF decode."""

    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "baseline_hf_form_injected_plain"
