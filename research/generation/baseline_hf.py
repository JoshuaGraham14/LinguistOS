"""Baseline Hugging Face generation -- batched, local small models.

Mirrors ``baseline_gpt`` (same prompt, same batched request for N candidates)
but runs a local transformers chat model instead of the OpenAI API.

Small models frequently emit malformed JSON, so parsing is lenient:
strict JSON first, then first-{...}-block extraction, then a regex scrape of
"sentence"/"translation" pairs. If a call yields fewer than the requested
number of candidates, additional top-up calls are made (capped) so each case
still receives ~N sentences to evaluate. Per-call parse outcomes are printed
so degradation is visible in the run log.
"""

from __future__ import annotations

import json
import re
from typing import Any

from research.generation.base import BaseGenerator
from research.generation.prompt_builder import build_prompt, language_display_name

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


class BaselineHFGenerator(BaseGenerator):
    """Batched generation with a local Hugging Face chat model."""

    # One batched call like baseline_gpt, plus top-up calls if short.
    MAX_CALLS = 4

    def __init__(self, model: str = "Qwen/Qwen2.5-0.5B-Instruct", temperature: float = 0.7):
        self._model_id = model
        self._temperature = temperature

    @property
    def name(self) -> str:
        return "baseline_hf"

    def _call(self, prompt: str, system: str, max_new_tokens: int) -> str:
        import torch

        tokenizer, model = _load_model(self._model_id)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        template_kwargs: dict[str, Any] = {
            "add_generation_prompt": True,
            "tokenize": False,
        }
        if _is_qwen3(self._model_id):
            template_kwargs["enable_thinking"] = False
        text = tokenizer.apply_chat_template(messages, **template_kwargs)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=self._temperature,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
            )
        prompt_len = inputs["input_ids"].shape[1]
        raw = tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)
        return _strip_thinking(raw)

    # Subclasses can override to inject the gold ``expected_form`` into the
    # prompt; ``None`` keeps the prompt byte-identical to the baseline.
    _INJECT_EXPECTED_FORM: bool = False

    def _resolve_inject_expected_form(self, constraints: dict[str, Any]) -> str | None:
        if not self._INJECT_EXPECTED_FORM:
            return None
        expected = constraints.get("expected_form")
        return str(expected) if expected else None

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
        system = (
            f"You are a helpful {lang} language tutor. "
            "Always respond with valid JSON."
        )
        inject_expected_form = self._resolve_inject_expected_form(constraints)

        collected: list[dict[str, str]] = []
        for call_idx in range(self.MAX_CALLS):
            remaining = num_candidates - len(collected)
            if remaining <= 0:
                break
            prompt = build_prompt(
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
            # ~60 tokens per candidate pair, plus JSON scaffolding headroom.
            max_new_tokens = min(80 * remaining + 200, 3072)
            raw = self._call(prompt, system, max_new_tokens)
            cands, mode = parse_candidates_lenient(raw)
            print(
                f"    [baseline_hf call {call_idx + 1}] requested={remaining} "
                f"parsed={len(cands)} mode={mode}"
            )
            collected.extend(cands)

        return collected[:num_candidates]


class FormInjectedHFGenerator(BaselineHFGenerator):
    """``baseline_hf`` with the gold ``expected_form`` injected into the prompt."""

    _INJECT_EXPECTED_FORM = True

    @property
    def name(self) -> str:
        return "baseline_hf_form_injected"
