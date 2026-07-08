#!/usr/bin/env python3
"""Diagnostic 4 — Spanish prompt ablation (frequency-validated, verbecc gold).

Paired prompt interventions on the same 150 Spanish verbs × 31 morphological cells
as Diagnostic 3C (4,650 cells per model):

- **Diagnostic 4A** (``diagnostic_4a``): ``build_prompt_explicit`` — production
  baseline + Spanish morphology overlay; T=0, 1 sample/cell; no gold form in prompt
  (indicative); participle cells mirror 3C participle scaffold + explicit overlay.
- **Diagnostic 4B** (``diagnostic_4b``): 3C pass@1 then one constraint-only rewrite
  on EF failure (no gold form in correction prompt). Pass@1 may be reused from
  completed Diagnostic 3C results when ``--reuse-3c-pass1`` (default if 3C file exists).

Compare 4A/4B against Diagnostic 3C (baseline) and binding gap vs Diagnostic 2A strict.

Part of the **Diagnostics** track; see ``research/diagnostics/registry.yaml``.

Output:
  docs/spike-results/eval_diagnostic_4a_n150_sentence_qwen_results.json
  docs/spike-results/eval_diagnostic_4b_n150_sentence_qwen_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Run:
  python3 -m research.prototyping.diagnostic_4_spanish_prompt_ablation_qwen_spike --dry-run
  python3 -m research.prototyping.diagnostic_4_spanish_prompt_ablation_qwen_spike \\
      --variant diagnostic_4a --models qwen17b --limit 5
  python3 -m research.prototyping.diagnostic_4_spanish_prompt_ablation_qwen_spike \\
      --variant diagnostic_4a --resume
  python3 -m research.prototyping.diagnostic_4_spanish_prompt_ablation_qwen_spike \\
      --variant diagnostic_4b --reuse-3c-pass1 --resume

Manifest: research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv
Models:    Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.length_bands import get_band
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.generation.baseline_hf import (
    _is_qwen3,
    _load_model,
    _strip_thinking,
    parse_candidates_lenient,
    unload_model,
)
from research.generation.languages import load_language_profile
from research.generation.prompt_builder import build_prompt_explicit
from research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike import (
    DEFAULT_MANIFEST,
    DEFAULT_MODEL_KEYS,
    INDICATIVE_TENSES,
    PARTICIPLE_TENSE,
    PERSON_NUMBER_SLOTS,
    QWEN_MODELS,
    TENSES,
    gold_form,
    gold_participle,
    load_manifest,
    wilson_ci,
)
from research.prototyping.diagnostic_3_spanish_sentence_qwen_spike import (
    DEFAULT_2A_RESULTS,
    SYSTEM_MESSAGE_PRODUCTION,
    build_prompt_3c_indicative,
    build_prompt_3c_participle,
    lemma_translation,
    load_2a_strict_index,
    summarize as summarize_binding,
)

Variant = Literal["diagnostic_4a", "diagnostic_4b"]
VARIANTS: tuple[Variant, ...] = ("diagnostic_4a", "diagnostic_4b")

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "spike-results"

DEFAULT_OUTPUTS: dict[Variant, Path] = {
    "diagnostic_4a": RESULTS_DIR / "eval_diagnostic_4a_n150_sentence_qwen_results.json",
    "diagnostic_4b": RESULTS_DIR / "eval_diagnostic_4b_n150_sentence_qwen_results.json",
}

DEFAULT_3C_RESULTS = RESULTS_DIR / "eval_diagnostic_3c_n150_sentence_qwen_results.json"

DIAGNOSTIC_SERIES = "diagnostic_4"
DIAGNOSTIC_SERIES_TITLE = "Spanish prompt ablation (explicit vs self-correct)"
DIAGNOSTIC_SERIES_LABEL = "Diagnostic 4 — Spanish prompt ablation (frequency-validated)"

SENTENCE_LENGTH = "short"
TEMPERATURE = 0.0
SAMPLES_PER_CELL = 1

VARIANT_META: dict[Variant, dict[str, Any]] = {
    "diagnostic_4a": {
        "diagnostic_id": "diagnostic_4a",
        "diagnostic_number": "4A",
        "diagnostic_title": "Spanish prompt ablation (explicit overlay)",
        "diagnostic_label": "Diagnostic 4A — explicit overlay on 3C scaffold",
        "prompt_version": "build_prompt_explicit_v1",
    },
    "diagnostic_4b": {
        "diagnostic_id": "diagnostic_4b",
        "diagnostic_number": "4B",
        "diagnostic_title": "Spanish prompt ablation (self-correct)",
        "diagnostic_label": "Diagnostic 4B — 3C pass@1 + constraint-only rewrite",
        "prompt_version": "build_prompt_baseline_v1 + correction_v1",
    },
}

_EF = ExpectedFormMatchEvaluator()


@dataclass
class SentenceCase:
    id: str
    variant: Variant
    lemma: str
    cell_id: str
    zipf: float
    tier: str
    irregular_probed: bool
    tense: str
    person: str
    number: str
    person_label: str
    expected_form: str
    prompt: str
    pass1_prompt: str = ""
    translation: str = ""
    num_candidates: int = 1
    is_participle: bool = False
    constraints: dict[str, str] = field(default_factory=dict)


def normalize_variant(value: str) -> Variant:
    if value in VARIANTS:
        return value  # type: ignore[return-value]
    raise ValueError(f"Unknown variant: {value!r}; expected one of {VARIANTS}")


def variant_config(variant: Variant) -> dict[str, Any]:
    return VARIANT_META[variant]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1"}


def _participle_explicit_overlay(*, sentence_length: str) -> str:
    lo, hi = get_band(sentence_length)
    return (
        "Additional requirements:\n"
        f"- Length: {lo}–{hi} words per sentence.\n"
        "- The participle must appear as one token — not the bare infinitive.\n"
    )


def build_prompt_4a_indicative(
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    num_candidates: int,
    sentence_length: str,
) -> str:
    return build_prompt_explicit(
        keyword=lemma,
        translation=lemma_translation(lemma),
        target_language="es",
        constraints={"tense": tense, "person": person, "number": number},
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=None,
    )


def build_prompt_4a_participle(
    lemma: str,
    *,
    participle: str,
    num_candidates: int,
    sentence_length: str,
) -> str:
    base = build_prompt_3c_participle(
        lemma,
        participle=participle,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
    )
    return base + "\n" + _participle_explicit_overlay(sentence_length=sentence_length)


def build_prompt_4b_pass1_indicative(
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    num_candidates: int,
    sentence_length: str,
) -> str:
    return build_prompt_3c_indicative(
        lemma,
        tense=tense,
        person=person,
        number=number,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
    )


def build_prompt_4b_pass1_participle(
    lemma: str,
    *,
    participle: str,
    num_candidates: int,
    sentence_length: str,
) -> str:
    return build_prompt_3c_participle(
        lemma,
        participle=participle,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
    )


def build_case_prompts(
    variant: Variant,
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    expected_form: str,
    is_participle: bool,
    num_candidates: int,
) -> tuple[str, str]:
    """Return (primary_prompt, pass1_prompt). pass1_prompt is 3C baseline for 4B."""
    if variant == "diagnostic_4a":
        if is_participle:
            prompt = build_prompt_4a_participle(
                lemma,
                participle=expected_form,
                num_candidates=num_candidates,
                sentence_length=SENTENCE_LENGTH,
            )
        else:
            prompt = build_prompt_4a_indicative(
                lemma,
                tense=tense,
                person=person,
                number=number,
                num_candidates=num_candidates,
                sentence_length=SENTENCE_LENGTH,
            )
        return prompt, prompt

    if is_participle:
        pass1 = build_prompt_4b_pass1_participle(
            lemma,
            participle=expected_form,
            num_candidates=num_candidates,
            sentence_length=SENTENCE_LENGTH,
        )
    else:
        pass1 = build_prompt_4b_pass1_indicative(
            lemma,
            tense=tense,
            person=person,
            number=number,
            num_candidates=num_candidates,
            sentence_length=SENTENCE_LENGTH,
        )
    return pass1, pass1


def _constraint_summary(constraints: dict[str, str], *, is_participle: bool = False) -> str:
    if is_participle:
        return "past participle (participio pasado)"
    profile = load_language_profile("es")
    parts: list[str] = []
    for field_name in profile.dimension_fields():
        if field_name not in constraints:
            continue
        label = profile.label_for(field_name)
        display = profile.gloss_for(field_name, str(constraints[field_name]))
        parts.append(f"{label}: {display}")
    return "; ".join(parts) if parts else "see original task constraints"


def build_correction_prompt(case: SentenceCase, *, sentence: str, translation: str) -> str:
    summary = _constraint_summary(case.constraints, is_participle=case.is_participle)
    lemma = case.lemma
    gloss = case.translation or lemma
    if case.is_participle:
        task_line = (
            f'The Spanish sentence below may not correctly include the past participle '
            f'of "{lemma}" (English: "{gloss}").\n'
        )
        infinitive_line = f'Do not leave the verb as the bare infinitive "{lemma}".\n'
    else:
        task_line = (
            f'The Spanish sentence below may not correctly conjugate the verb '
            f'"{lemma}" (English: "{gloss}").\n'
        )
        infinitive_line = f'Do not leave the verb as the infinitive "{lemma}".\n'
    return (
        task_line
        + f"Required morphology: {summary}.\n"
        + infinitive_line
        + "Review the sentence and rewrite it so the verb form matches the constraints.\n"
        'Reply ONLY as JSON: {"sentence":"...","translation":"..."}\n\n'
        f"Original sentence: {sentence}\n"
        f"Original translation: {translation}"
    )


def build_cases(
    manifest_rows: list[dict[str, str]],
    *,
    variant: Variant,
    limit: int | None = None,
) -> list[SentenceCase]:
    cases: list[SentenceCase] = []

    for row in manifest_rows:
        lemma = row["verb"]
        participle = gold_participle(row)
        translation = lemma_translation(lemma)
        base = {
            "variant": variant,
            "lemma": lemma,
            "cell_id": row["cell_id"],
            "zipf": float(row["zipf"]),
            "tier": row["tier"],
            "irregular_probed": _parse_bool(row["irregular_probed"]),
            "translation": translation,
            "num_candidates": SAMPLES_PER_CELL,
        }

        for tense in INDICATIVE_TENSES:
            for person, number, label in PERSON_NUMBER_SLOTS:
                expected = gold_form(lemma, tense, person, number)
                prompt, pass1 = build_case_prompts(
                    variant,
                    lemma,
                    tense=tense,
                    person=person,
                    number=number,
                    expected_form=expected,
                    is_participle=False,
                    num_candidates=SAMPLES_PER_CELL,
                )
                cases.append(
                    SentenceCase(
                        id=f"{lemma}__{tense}__{person}_{number}",
                        tense=tense,
                        person=person,
                        number=number,
                        person_label=label,
                        expected_form=expected,
                        prompt=prompt,
                        pass1_prompt=pass1,
                        constraints={"tense": tense, "person": person, "number": number},
                        **base,
                    )
                )

        prompt, pass1 = build_case_prompts(
            variant,
            lemma,
            tense=PARTICIPLE_TENSE,
            person="",
            number="",
            expected_form=participle,
            is_participle=True,
            num_candidates=SAMPLES_PER_CELL,
        )
        cases.append(
            SentenceCase(
                id=f"{lemma}__{PARTICIPLE_TENSE}",
                tense=PARTICIPLE_TENSE,
                person="",
                number="",
                person_label="participle",
                expected_form=participle,
                prompt=prompt,
                pass1_prompt=pass1,
                is_participle=True,
                constraints={},
                **base,
            )
        )

    if limit is not None:
        cases = cases[:limit]
    return cases


def _score_one_sentence(sentence: str, expected_form: str) -> dict[str, Any]:
    ef = _EF.evaluate(sentence, "", {"expected_form": expected_form})
    passed = bool(ef.details.get("passed"))
    return {
        "sentence": sentence,
        "expected_form_pass": passed,
        "matched_token": ef.details.get("matched_token"),
        "tokens_checked": ef.details.get("tokens_checked"),
    }


def _score_json_raw(raw: str, case: SentenceCase) -> dict[str, Any]:
    cands, parse_mode = parse_candidates_lenient(_strip_thinking(raw))
    scored_cands: list[dict[str, Any]] = []
    for cand in cands:
        sentence = str(cand.get("sentence", "")).strip()
        translation = str(cand.get("translation", "")).strip()
        one = _score_one_sentence(sentence, case.expected_form)
        scored_cands.append({"sentence": sentence, "translation": translation, **one})

    first = scored_cands[0] if scored_cands else None
    return {
        "raw": raw.strip(),
        "parse_mode": parse_mode,
        "candidates": scored_cands,
        "n_candidates_parsed": len(scored_cands),
        "sentence": first["sentence"] if first else "",
        "translation": first["translation"] if first else "",
        "expected_form_pass": bool(first and first["expected_form_pass"]),
        "pass_at_1": bool(first and first["expected_form_pass"]),
        "matched_token": first["matched_token"] if first else None,
        "tokens_checked": first["tokens_checked"] if first else 0,
    }


def _max_new_tokens(num_candidates: int) -> int:
    return min(80 * num_candidates + 200, 3072)


def _run_generation(
    model_id: str,
    prompt: str,
    *,
    temperature: float,
    max_new_tokens: int,
) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE_PRODUCTION},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {"add_generation_prompt": True, "tokenize": False}
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if temperature <= 0:
        gen_kwargs["do_sample"] = False
    else:
        gen_kwargs["do_sample"] = True
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = 0.9

    with torch.no_grad():
        output = model.generate(**inputs, **gen_kwargs)
    prompt_len = inputs["input_ids"].shape[1]
    return _strip_thinking(tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True))


def _pass1_from_3c_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sentence": row.get("sentence", ""),
        "translation": row.get("translation", ""),
        "expected_form_pass": bool(row.get("expected_form_pass")),
        "pass_at_1": bool(row.get("expected_form_pass")),
        "raw": row.get("raw", ""),
        "parse_mode": row.get("parse_mode"),
        "matched_token": row.get("matched_token"),
        "tokens_checked": row.get("tokens_checked"),
        "reused_from_3c": True,
    }


def load_3c_index(path: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    """Map model_key -> case_id -> result row from Diagnostic 3C, plus payload metadata."""
    if not path.is_file():
        return {}, {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for model_key, block in payload.get("by_model", {}).items():
        index: dict[str, dict[str, Any]] = {}
        for row in block.get("results", []):
            case_id = row.get("case", {}).get("id")
            if case_id:
                index[case_id] = row
        out[model_key] = index
    meta = {
        "manifest_path": payload.get("manifest_path"),
        "variant": payload.get("variant"),
        "n_probes": payload.get("n_probes"),
    }
    return out, meta


def _warn_if_3c_mismatch(
    d3c_meta: dict[str, Any],
    *,
    manifest_path: Path,
    n_probes: int,
    d3c_results_path: Path,
) -> None:
    if not d3c_meta:
        return
    expected_variant = d3c_meta.get("variant")
    if expected_variant and expected_variant != "diagnostic_3c":
        print(
            f"WARNING: {d3c_results_path} variant is {expected_variant!r}, expected 'diagnostic_3c'.",
            flush=True,
        )
    expected_manifest = d3c_meta.get("manifest_path")
    if expected_manifest and Path(expected_manifest).resolve() != manifest_path.resolve():
        print(
            f"WARNING: 3C manifest {expected_manifest} != current {manifest_path} — "
            "pass@1 reuse may be invalid.",
            flush=True,
        )
    expected_n = d3c_meta.get("n_probes")
    if expected_n is not None and expected_n != n_probes:
        print(
            f"WARNING: 3C n_probes={expected_n} != current {n_probes} — partial reuse only.",
            flush=True,
        )


def _rate_bool(values: list[bool]) -> dict[str, Any]:
    n = len(values)
    k = sum(1 for v in values if v)
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def _paired_vs_3c(
    rows: list[dict[str, Any]],
    d3c_index: dict[str, dict[str, Any]],
    *,
    pass_key: str = "expected_form_pass",
) -> dict[str, Any]:
    paired = 0
    rescued = 0
    hurt = 0
    both_pass = 0
    both_fail = 0
    for row in rows:
        case_id = row["case"]["id"]
        d3c_row = d3c_index.get(case_id)
        if d3c_row is None:
            continue
        paired += 1
        p3c = bool(d3c_row.get("expected_form_pass"))
        p4 = bool(row.get(pass_key))
        if p3c and p4:
            both_pass += 1
        elif not p3c and not p4:
            both_fail += 1
        elif not p3c and p4:
            rescued += 1
        else:
            hurt += 1
    return {
        "paired_cells": paired,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "rescued_3c_fail_4_pass": rescued,
        "hurt_3c_pass_4_fail": hurt,
        "net_gain_cells": rescued - hurt,
    }


def summarize_4b(rows: list[dict[str, Any]], d3c_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pass_at_1 = [bool(r.get("pass_at_1")) for r in rows]
    pass_at_2 = [bool(r.get("pass_at_2")) for r in rows]
    failures = sum(1 for p in pass_at_1 if not p)
    corrected = sum(1 for r in rows if r.get("corrected"))
    fixes = sum(
        1 for r in rows
        if r.get("corrected") and r.get("pass_at_2") and not r.get("pass_at_1")
    )
    reused = sum(1 for r in rows if r.get("pass1_reused_from_3c"))

    out: dict[str, Any] = {
        "pass_at_1": _rate_bool(pass_at_1),
        "pass_at_2": _rate_bool(pass_at_2),
        "correction": {
            "failures_at_1": failures,
            "correction_attempts": corrected,
            "corrections_successful": fixes,
            "correction_yield": round(fixes / failures, 4) if failures else None,
            "pass1_reused_from_3c": reused,
        },
        "paired_vs_3c_pass_at_1": _paired_vs_3c(rows, d3c_index, pass_key="pass_at_1"),
    }
    return out


def summarize_payload(
    payload: dict[str, Any],
    *,
    d2a_index_by_model: dict[str, dict[str, bool]],
    d3c_index_by_model: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    variant = payload.get("variant", "diagnostic_4a")
    binding = summarize_binding(payload, d2a_index_by_model=d2a_index_by_model)
    out: dict[str, Any] = {"per_model": {}, "variant": variant}

    for key, block in binding.get("per_model", {}).items():
        per_model = dict(block)
        d3c_index = d3c_index_by_model.get(key, {})
        rows = payload["by_model"][key]["results"]

        if variant == "diagnostic_4a":
            per_model["paired_vs_3c"] = _paired_vs_3c(rows, d3c_index)
        elif variant == "diagnostic_4b":
            per_model.update(summarize_4b(rows, d3c_index))

        out["per_model"][key] = per_model
    return out


def _save_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_spike_4a(
    cases: list[SentenceCase],
    model_keys: list[str],
    *,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path,
    d2a_results_path: Path,
    d3c_results_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    variant: Variant = "diagnostic_4a"
    meta = variant_config(variant)
    d2a_index_by_model = load_2a_strict_index(d2a_results_path)
    d3c_index_by_model, d3c_meta = load_3c_index(d3c_results_path)
    _warn_if_3c_mismatch(
        d3c_meta,
        manifest_path=manifest_path,
        n_probes=len(cases),
        d3c_results_path=d3c_results_path,
    )

    payload: dict[str, Any] | None = None
    if resume and output_path.is_file():
        with output_path.open(encoding="utf-8") as f:
            payload = json.load(f)
        done = set(payload.get("by_model", {}))
        model_keys = [k for k in model_keys if k not in done]
        if not model_keys:
            print(f"All requested models already in {output_path}", flush=True)
            return payload
        print(f"Resuming {variant}; remaining models: {model_keys}", flush=True)

    if payload is None:
        payload = _new_payload(
            variant,
            meta,
            model_keys,
            manifest_path,
            manifest_rows,
            d2a_results_path,
            d3c_results_path,
            n_probes=len(cases),
        )

    for key in model_keys:
        model_id = QWEN_MODELS[key]
        print(f"\n=== {variant} / {key} ({model_id}) ===")
        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.id}...", flush=True)
            t_case = time.perf_counter()
            raw = _run_generation(
                model_id,
                case.prompt,
                temperature=TEMPERATURE,
                max_new_tokens=_max_new_tokens(case.num_candidates),
            )
            scored = _score_json_raw(raw, case)
            rows.append(
                {
                    "case": asdict(case),
                    "latency_s": round(time.perf_counter() - t_case, 3),
                    **scored,
                }
            )
        payload["by_model"][key] = {
            "model_id": model_id,
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "results": rows,
        }
        payload["summary"] = summarize_payload(
            payload,
            d2a_index_by_model=d2a_index_by_model,
            d3c_index_by_model=d3c_index_by_model,
        )
        _save_payload(payload, output_path)
        print(f"  checkpoint saved → {output_path}", flush=True)
        unload_model(model_id)
    return payload


def run_spike_4b(
    cases: list[SentenceCase],
    model_keys: list[str],
    *,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path,
    d2a_results_path: Path,
    d3c_results_path: Path,
    reuse_3c_pass1: bool,
    resume: bool = False,
) -> dict[str, Any]:
    variant: Variant = "diagnostic_4b"
    meta = variant_config(variant)
    d2a_index_by_model = load_2a_strict_index(d2a_results_path)
    d3c_index_by_model, d3c_meta = load_3c_index(d3c_results_path)
    _warn_if_3c_mismatch(
        d3c_meta,
        manifest_path=manifest_path,
        n_probes=len(cases),
        d3c_results_path=d3c_results_path,
    )

    if reuse_3c_pass1 and not d3c_index_by_model:
        print(
            f"WARNING: --reuse-3c-pass1 set but {d3c_results_path} missing or empty; "
            "will run pass@1 inline.",
            flush=True,
        )
        reuse_3c_pass1 = False

    payload: dict[str, Any] | None = None
    if resume and output_path.is_file():
        with output_path.open(encoding="utf-8") as f:
            payload = json.load(f)
        done = set(payload.get("by_model", {}))
        model_keys = [k for k in model_keys if k not in done]
        if not model_keys:
            print(f"All requested models already in {output_path}", flush=True)
            return payload
        print(f"Resuming {variant}; remaining models: {model_keys}", flush=True)

    if payload is None:
        payload = _new_payload(
            variant,
            meta,
            model_keys,
            manifest_path,
            manifest_rows,
            d2a_results_path,
            d3c_results_path,
            extra={
                "reuse_3c_pass1": reuse_3c_pass1,
                "diagnostic_3c_results_path": str(d3c_results_path),
            },
            n_probes=len(cases),
        )

    for key in model_keys:
        model_id = QWEN_MODELS[key]
        d3c_for_model = d3c_index_by_model.get(key, {})
        print(f"\n=== {variant} / {key} ({model_id}) ===")
        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.id}...", flush=True)
            t_case = time.perf_counter()

            pass1_reused = False
            d3c_row = d3c_for_model.get(case.id) if reuse_3c_pass1 else None
            if d3c_row is not None:
                pass1 = _pass1_from_3c_row(d3c_row)
                pass1_reused = True
            else:
                raw1 = _run_generation(
                    model_id,
                    case.pass1_prompt,
                    temperature=TEMPERATURE,
                    max_new_tokens=_max_new_tokens(case.num_candidates),
                )
                pass1 = _score_json_raw(raw1, case)

            pass_at_1 = bool(pass1.get("pass_at_1"))
            corrected = False
            pass_at_2 = pass_at_1
            correction_raw = None
            correction_prompt = None

            if not pass_at_1:
                correction_prompt = build_correction_prompt(
                    case,
                    sentence=str(pass1.get("sentence", "")),
                    translation=str(pass1.get("translation", "")),
                )
                correction_raw = _run_generation(
                    model_id,
                    correction_prompt,
                    temperature=TEMPERATURE,
                    max_new_tokens=256,
                )
                corrected = True
                fix = _score_json_raw(correction_raw, case)
                pass_at_2 = bool(fix.get("expected_form_pass"))
                pass1["corrected_sentence"] = fix.get("sentence")
                pass1["corrected_translation"] = fix.get("translation")
                pass1["correction_raw"] = correction_raw
                pass1["correction_parse_mode"] = fix.get("parse_mode")

            rows.append(
                {
                    "case": asdict(case),
                    "latency_s": round(time.perf_counter() - t_case, 3),
                    **pass1,
                    "pass1_reused_from_3c": pass1_reused,
                    "correction_prompt": correction_prompt,
                    "corrected": corrected,
                    "pass_at_1": pass_at_1,
                    "pass_at_2": pass_at_2,
                    "expected_form_pass": pass_at_2,
                    "sentence": (
                        pass1.get("corrected_sentence")
                        if corrected and pass_at_2
                        else pass1.get("sentence")
                    ),
                    "translation": (
                        pass1.get("corrected_translation")
                        if corrected and pass_at_2
                        else pass1.get("translation")
                    ),
                }
            )

        payload["by_model"][key] = {
            "model_id": model_id,
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "results": rows,
        }
        payload["summary"] = summarize_payload(
            payload,
            d2a_index_by_model=d2a_index_by_model,
            d3c_index_by_model=d3c_index_by_model,
        )
        _save_payload(payload, output_path)
        print(f"  checkpoint saved → {output_path}", flush=True)
        unload_model(model_id)
    return payload


def _new_payload(
    variant: Variant,
    meta: dict[str, Any],
    model_keys: list[str],
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    d2a_results_path: Path,
    d3c_results_path: Path,
    *,
    n_probes: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "diagnostic_series": DIAGNOSTIC_SERIES,
        "diagnostic_series_title": DIAGNOSTIC_SERIES_TITLE,
        "diagnostic_id": meta["diagnostic_id"],
        "diagnostic_number": meta["diagnostic_number"],
        "diagnostic_title": meta["diagnostic_title"],
        "diagnostic_label": meta["diagnostic_label"],
        "related_diagnostics": ["diagnostic_2a", "diagnostic_3c"],
        "related_experiments": [4, 5],
        "variant": variant,
        "prompt_version": meta["prompt_version"],
        "scoring_metric": "expected_form_match",
        "manifest_path": str(manifest_path),
        "manifest_seed": manifest_rows[0].get("seed") if manifest_rows else None,
        "diagnostic_2a_results_path": str(d2a_results_path),
        "diagnostic_3c_results_path": str(d3c_results_path),
        "n_verbs": len(manifest_rows),
        "n_probes": n_probes,
        "indicative_tenses": list(INDICATIVE_TENSES),
        "tenses": list(TENSES),
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "temperature": TEMPERATURE,
        "samples_per_cell": SAMPLES_PER_CELL,
        "cefr_level": None,
        "sentence_length": SENTENCE_LENGTH,
        "output_format": "json",
        "gold_source": "verbecc (+ manifest gold_participle where present)",
        "by_model": {},
    }
    if extra:
        payload.update(extra)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{DIAGNOSTIC_SERIES_LABEL} — explicit overlay and self-correct.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Verb manifest CSV (default: manifest_diagnostic_2_paradigm_n150.csv).",
    )
    parser.add_argument(
        "--variant",
        choices=VARIANTS,
        default="diagnostic_4a",
        help="Diagnostic 4 variant (default: diagnostic_4a).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=None,
    )
    parser.add_argument("--limit", type=int, default=None, help="First N probes only.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None, help="Override output JSON path.")
    parser.add_argument(
        "--d2a-results",
        type=Path,
        default=DEFAULT_2A_RESULTS,
        help="Diagnostic 2A results JSON for binding-gap summary.",
    )
    parser.add_argument(
        "--d3c-results",
        type=Path,
        default=DEFAULT_3C_RESULTS,
        help="Diagnostic 3C results JSON for paired comparison / pass@1 reuse.",
    )
    parser.add_argument(
        "--reuse-3c-pass1",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="4B only: reuse pass@1 from 3C (default: on if 3C results file exists).",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    variant = normalize_variant(args.variant)
    model_keys = list(DEFAULT_MODEL_KEYS) if args.models is None else args.models
    manifest_rows = load_manifest(args.manifest)
    cases = build_cases(manifest_rows, variant=variant, limit=args.limit)

    reuse_3c = args.reuse_3c_pass1
    if variant == "diagnostic_4b" and reuse_3c is None:
        reuse_3c = args.d3c_results.is_file()

    if args.dry_run:
        print(f"{DIAGNOSTIC_SERIES_LABEL}")
        print(f"Variant: {variant}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} Spanish verbs)")
        print(f"Probes: {len(cases)} ({len(manifest_rows)} verbs × 31 cells)")
        print(f"Models: {model_keys}")
        print(f"Temperature: {TEMPERATURE}")
        print(f"Samples per cell: {SAMPLES_PER_CELL}")
        print(f"Sentence length: {SENTENCE_LENGTH}")
        print(f"CEFR: None (matched to 3C)")
        print(f"System: {SYSTEM_MESSAGE_PRODUCTION!r}")
        print(f"3C results for pairing: {args.d3c_results} (exists={args.d3c_results.is_file()})")
        if variant == "diagnostic_4b":
            print(f"Reuse 3C pass@1: {reuse_3c}")
        for case in cases[:3]:
            print(f"\n--- {case.id} → {case.expected_form} ---")
            print(case.prompt[:800])
            if variant == "diagnostic_4b":
                print("\n[correction template uses pass@1 sentence when EF fails]")
        if len(cases) > 3:
            print(f"\n... and {len(cases) - 3} more")
        return

    output_path = args.output or DEFAULT_OUTPUTS[variant]
    if variant == "diagnostic_4a":
        data = run_spike_4a(
            cases,
            model_keys,
            manifest_path=args.manifest,
            manifest_rows=manifest_rows,
            output_path=output_path,
            d2a_results_path=args.d2a_results,
            d3c_results_path=args.d3c_results,
            resume=args.resume,
        )
    else:
        data = run_spike_4b(
            cases,
            model_keys,
            manifest_path=args.manifest,
            manifest_rows=manifest_rows,
            output_path=output_path,
            d2a_results_path=args.d2a_results,
            d3c_results_path=args.d3c_results,
            reuse_3c_pass1=bool(reuse_3c),
            resume=args.resume,
        )

    print(f"\n--- Summary ({variant}) ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"Full results: {output_path}")


if __name__ == "__main__":
    main()
