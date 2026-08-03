"""OpenAI plain Fix-B generation — same prompt as ``baseline_hf_plain_b``.

Used for frontier ceiling runs (e.g. GPT-5.5 on ``spanish_lora_ood_n36``) so
the comparison with Qwen vanilla Fix-B is prompt-fair: plain text out, full
sentence requirements, no gold-form inject, no JSON scaffold.
"""

from __future__ import annotations

import os
import time
from typing import Any

from research.generation.base import BaseGenerator
from research.generation.plain_output import candidate_from_plain
from research.generation.prompt_builder import build_prompt_plain, language_display_name

_DEFAULT_MODEL = "gpt-5.5"
_DEFAULT_REASONING_EFFORT = "low"
_MAX_RETRIES = 6


def _system_prompt(lang: str) -> str:
    """Match ``PlainHFGenerator._generation_system_prompt``."""
    return (
        f"You are a helpful {lang} language tutor. "
        "Reply with exactly one Spanish sentence per request."
    )


def generate_plain_b(
    keyword: str,
    translation: str,
    constraints: dict[str, Any],
    num_candidates: int = 1,
    *,
    target_language: str = "es",
    cefr_level: str | None = None,
    sentence_length: str = "short",
    explicit_subject_required: bool = False,
    model: str = _DEFAULT_MODEL,
    temperature: float = 0.0,
    reasoning_effort: str | None = _DEFAULT_REASONING_EFFORT,
    api_key: str | None = None,
    inject_expected_form: str | None = None,
) -> list[dict[str, str]]:
    """Call OpenAI with the Fix-B plain prompt; return parsed candidates."""
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return []

    from openai import OpenAI

    client = OpenAI(api_key=key)
    lang = language_display_name(target_language)
    # One sentence per API call (same as PlainHF ``_max_candidates_per_call``).
    out: list[dict[str, str]] = []
    for _ in range(max(1, num_candidates)):
        user_prompt = build_prompt_plain(
            keyword=keyword,
            translation=translation,
            target_language=target_language,
            constraints=constraints,
            num_candidates=1,
            sentence_length=sentence_length,
            cefr_level=cefr_level,
            explicit_subject_required=explicit_subject_required,
            inject_expected_form=inject_expected_form,
            require_full_sentence=True,
            morphology_hints=False,
        )
        raw = _chat_once(
            client,
            model=model,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            system=_system_prompt(lang),
            user=user_prompt,
        )
        cand, _mode = candidate_from_plain(raw)
        if cand["sentence"]:
            out.append(cand)
    return out


def _chat_once(
    client: Any,
    *,
    model: str,
    temperature: float,
    reasoning_effort: str | None,
    system: str,
    user: str,
) -> str:
    """Chat Completions with retries; tolerate models that reject temperature."""
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
            # Prefer greedy for parity with Qwen vanilla (temp=0). Some reasoning
            # models reject temperature — fall through without it on TypeError /
            # BadRequestError once.
            try:
                kwargs_with_temp = {**kwargs, "temperature": temperature}
                completion = client.chat.completions.create(**kwargs_with_temp)
            except Exception as temp_err:
                msg = str(temp_err).lower()
                if "temperature" in msg:
                    completion = client.chat.completions.create(**kwargs)
                else:
                    raise temp_err
            return completion.choices[0].message.content or ""
        except Exception as err:
            last_err = err
            msg = str(err).lower()
            retryable = any(
                token in msg
                for token in ("rate limit", "429", "timeout", "503", "502", "overloaded")
            )
            if not retryable or attempt + 1 >= _MAX_RETRIES:
                break
            time.sleep(min(2 ** attempt, 30))
    if last_err is not None:
        raise last_err
    return ""


class PlainGPTBGenerator(BaseGenerator):
    """Fix-B plain OpenAI generator (no form inject)."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        temperature: float = 0.0,
        reasoning_effort: str = _DEFAULT_REASONING_EFFORT,
    ):
        self._model = model
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort

    @property
    def name(self) -> str:
        return "baseline_gpt_plain_b"

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
        return generate_plain_b(
            keyword=keyword,
            translation=translation,
            constraints=constraints,
            num_candidates=num_candidates,
            target_language=target_language,
            cefr_level=cefr_level,
            sentence_length=sentence_length,
            explicit_subject_required=explicit_subject_required,
            model=self._model,
            temperature=self._temperature,
            reasoning_effort=self._reasoning_effort,
        )
