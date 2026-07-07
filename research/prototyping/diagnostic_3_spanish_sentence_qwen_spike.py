#!/usr/bin/env python3
"""Diagnostic 3 — Spanish sentence binding (frequency-validated, verbecc gold).

Paired sentence probes on the same 150 Spanish verbs as Diagnostic 2A:

- **Diagnostic 3A** (``diagnostic_3a``): plain-text sentence, 2A-aligned tense/person
  hints, no length band, no JSON, no CEFR — compare slot-level pass to 2A strict.

Part of the **Diagnostics** track; see ``research/diagnostics/registry.yaml``.

Output:
  docs/spike-results/eval_diagnostic_3a_n150_sentence_qwen_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Run:
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike --dry-run
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3a --models qwen17b --limit 5
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3a --resume

Manifest: research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv
Models:    Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B (thinking disabled)
Decoding:  Greedy (temperature=0); 1 sentence per morphological cell
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking, unload_model
from research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike import (
    DEFAULT_MANIFEST,
    DEFAULT_MODEL_KEYS,
    INDICATIVE_TENSES,
    PARTICIPLE_FORM_LABEL,
    PARTICIPLE_TENSE,
    PERSON_NUMBER_SLOTS,
    QWEN_MODELS,
    SUBJECT_HINTS,
    TENSE_PHRASE,
    TENSES,
    gold_form,
    gold_participle,
    load_manifest,
    wilson_ci,
)

Variant = Literal["diagnostic_3a"]
VARIANTS: tuple[Variant, ...] = ("diagnostic_3a",)

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "spike-results"

DEFAULT_OUTPUTS: dict[Variant, Path] = {
    "diagnostic_3a": RESULTS_DIR / "eval_diagnostic_3a_n150_sentence_qwen_results.json",
}

DEFAULT_2A_RESULTS = RESULTS_DIR / "eval_diagnostic_2a_n150_paradigm_qwen_results.json"

DIAGNOSTIC_SERIES = "diagnostic_3"
DIAGNOSTIC_SERIES_TITLE = "Spanish sentence binding vs paradigm recall"
DIAGNOSTIC_SERIES_LABEL = "Diagnostic 3 — Spanish sentence binding (frequency-validated)"

VARIANT_META: dict[Variant, dict[str, str]] = {
    "diagnostic_3a": {
        "diagnostic_id": "diagnostic_3a",
        "diagnostic_number": "3A",
        "diagnostic_title": "Spanish sentence binding (2A-aligned hints, plain text)",
        "diagnostic_label": "Diagnostic 3A — Spanish sentence binding (plain text)",
        "prompt_version": "sentence_3a_v1",
    },
}

SYSTEM_MESSAGE_3A = (
    "You are a Spanish language assistant. Follow the instruction exactly."
)

_JSONish_RE = re.compile(r"^\s*[\[{]")
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
    is_participle: bool = False


def normalize_variant(value: str) -> Variant:
    if value in VARIANTS:
        return value  # type: ignore[return-value]
    raise ValueError(f"Unknown variant: {value!r}; expected one of {VARIANTS}")


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1"}


def build_prompt_3a(
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    expected_form: str,
    is_participle: bool,
) -> str:
    if is_participle:
        return (
            "Write one natural Spanish sentence for vocabulary practice.\n"
            f'The sentence must contain the {PARTICIPLE_FORM_LABEL} of "{lemma}" '
            f'— the word "{expected_form}" must appear in the sentence, '
            f'not the bare infinitive "{lemma}".\n'
            "Reply with only the Spanish sentence, nothing else."
        )

    tense_label = TENSE_PHRASE.get(tense, tense)
    subject_hint = SUBJECT_HINTS[(person, number)]
    return (
        "Write one natural Spanish sentence for vocabulary practice.\n"
        f'The verb "{lemma}" must appear inflected in the {tense_label} '
        f"for {subject_hint} ({person} person, {number}) — "
        "not as the bare infinitive.\n"
        "Reply with only the Spanish sentence, nothing else."
    )


def build_prompt(case: SentenceCase) -> str:
    if case.variant == "diagnostic_3a":
        return case.prompt
    raise ValueError(f"No prompt builder for variant {case.variant!r}")


def system_message(variant: Variant) -> str:
    if variant == "diagnostic_3a":
        return SYSTEM_MESSAGE_3A
    raise ValueError(f"No system message for variant {variant!r}")


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
        base = {
            "variant": variant,
            "lemma": lemma,
            "cell_id": row["cell_id"],
            "zipf": float(row["zipf"]),
            "tier": row["tier"],
            "irregular_probed": _parse_bool(row["irregular_probed"]),
        }

        for tense in INDICATIVE_TENSES:
            for person, number, label in PERSON_NUMBER_SLOTS:
                expected = gold_form(lemma, tense, person, number)
                prompt = build_prompt_3a(
                    lemma,
                    tense=tense,
                    person=person,
                    number=number,
                    expected_form=expected,
                    is_participle=False,
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
                        **base,
                    )
                )

        prompt = build_prompt_3a(
            lemma,
            tense=PARTICIPLE_TENSE,
            person="",
            number="",
            expected_form=participle,
            is_participle=True,
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
                is_participle=True,
                **base,
            )
        )

    if limit is not None:
        cases = cases[:limit]
    return cases


def extract_sentence(raw: str) -> str:
    """Take the first usable sentence line from plain model output."""
    cleaned = _strip_thinking(raw).strip()
    if not cleaned:
        return ""

    # If the model ignored instructions and returned JSON, salvage sentence field.
    if _JSONish_RE.match(cleaned):
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                candidates = data.get("candidates")
                if isinstance(candidates, list) and candidates:
                    first = candidates[0]
                    if isinstance(first, dict):
                        sentence = str(first.get("sentence", "")).strip()
                        if sentence:
                            return sentence
        except json.JSONDecodeError:
            pass

    for line in cleaned.splitlines():
        line = line.strip().strip('"').strip("'")
        if line:
            return line
    return cleaned


def score_sentence(case: SentenceCase, raw: str) -> dict[str, Any]:
    sentence = extract_sentence(raw)
    ef = _EF.evaluate(sentence, "", {"expected_form": case.expected_form})
    passed = bool(ef.details.get("passed"))
    return {
        "raw": raw.strip(),
        "sentence": sentence,
        "expected_form_pass": passed,
        "matched_token": ef.details.get("matched_token"),
        "tokens_checked": ef.details.get("tokens_checked"),
    }


def _person_number_by_label() -> dict[str, tuple[str, str]]:
    return {label: (person, number) for person, number, label in PERSON_NUMBER_SLOTS}


def load_2a_strict_index(path: Path) -> dict[str, dict[str, bool]]:
    """Map model key -> sentence case id -> 2A strict slot pass."""
    if not path.is_file():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    label_to_pn = _person_number_by_label()
    out: dict[str, dict[str, bool]] = {}

    for model_key, block in payload.get("by_model", {}).items():
        index: dict[str, bool] = {}
        for row in block.get("results", []):
            case = row.get("case", {})
            lemma = case.get("lemma", "")
            tense = case.get("tense", "")
            if case.get("is_participle"):
                index[f"{lemma}__{PARTICIPLE_TENSE}"] = row.get("strict_slots_correct", 0) == 1
                continue

            for slot in row.get("per_person", []):
                person_label = slot.get("person", "")
                pn = label_to_pn.get(person_label)
                if pn is None:
                    continue
                person, number = pn
                case_id = f"{lemma}__{tense}__{person}_{number}"
                index[case_id] = bool(slot.get("strict_match"))
        out[model_key] = index

    return out


def _rate(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows
        if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n = len(filtered)
    k = sum(1 for r in filtered if r.get("expected_form_pass"))
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def _binding_gap(rows: list[dict[str, Any]], d2a_index: dict[str, bool]) -> dict[str, Any]:
    known = 0
    known_sentence_pass = 0
    gap = 0
    for row in rows:
        case_id = row["case"]["id"]
        if not d2a_index.get(case_id):
            continue
        known += 1
        if row.get("expected_form_pass"):
            known_sentence_pass += 1
        else:
            gap += 1
    lo, hi = wilson_ci(gap, known) if known else (None, None)
    return {
        "cells_known_in_2a": known,
        "cells_sentence_pass": known_sentence_pass,
        "binding_gap_cells": gap,
        "binding_gap_rate": round(gap / known, 4) if known else None,
        "sentence_pass_given_2a_known": round(known_sentence_pass / known, 4) if known else None,
        "binding_gap_wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize(
    payload: dict[str, Any],
    *,
    d2a_index_by_model: dict[str, dict[str, bool]],
) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}}
    for key, block in payload.get("by_model", {}).items():
        rows = block["results"]
        per_model: dict[str, Any] = {
            "overall": _rate(rows),
        }
        for tier in ("high", "mid", "low"):
            per_model[f"tier_{tier}"] = _rate(rows, tier=tier)
        for tense in TENSES:
            per_model[f"tense_{tense}"] = _rate(rows, tense=tense)

        d2a_index = d2a_index_by_model.get(key, {})
        if d2a_index:
            per_model["binding_gap_vs_2a_strict"] = _binding_gap(rows, d2a_index)
            for tier in ("high", "mid", "low"):
                tier_rows = [r for r in rows if r["case"].get("tier") == tier]
                per_model[f"binding_gap_tier_{tier}"] = _binding_gap(tier_rows, d2a_index)

        per_model["failures"] = [
            {
                "id": r["case"]["id"],
                "lemma": r["case"]["lemma"],
                "tense": r["case"]["tense"],
                "expected_form": r["case"]["expected_form"],
                "sentence": r.get("sentence"),
                "raw": r.get("raw"),
            }
            for r in rows
            if not r.get("expected_form_pass")
        ]
        out["per_model"][key] = per_model
    return out


def complete(model_id: str, case: SentenceCase, *, temperature: float) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    prompt = build_prompt(case)
    messages = [
        {"role": "system", "content": system_message(case.variant)},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {"add_generation_prompt": True, "tokenize": False}
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": 128,
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
    raw = tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)
    return _strip_thinking(raw)


def _save_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_spike(
    cases: list[SentenceCase],
    model_keys: list[str],
    *,
    variant: Variant,
    temperature: float,
    samples_per_cell: int,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path,
    d2a_results_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    if samples_per_cell != 1:
        raise ValueError("Diagnostic 3A uses samples_per_cell=1")

    meta = VARIANT_META[variant]
    d2a_index_by_model = load_2a_strict_index(d2a_results_path)

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
        payload = {
            "diagnostic_series": DIAGNOSTIC_SERIES,
            "diagnostic_series_title": DIAGNOSTIC_SERIES_TITLE,
            "diagnostic_id": meta["diagnostic_id"],
            "diagnostic_number": meta["diagnostic_number"],
            "diagnostic_title": meta["diagnostic_title"],
            "diagnostic_label": meta["diagnostic_label"],
            "related_diagnostics": ["diagnostic_2a"],
            "related_experiments": [3, "3B", 10],
            "variant": variant,
            "prompt_version": meta["prompt_version"],
            "scoring_metric": "expected_form_match",
            "manifest_path": str(manifest_path),
            "manifest_seed": manifest_rows[0].get("seed") if manifest_rows else None,
            "diagnostic_2a_results_path": str(d2a_results_path),
            "n_verbs": len(manifest_rows),
            "n_probes": len(cases),
            "indicative_tenses": list(INDICATIVE_TENSES),
            "tenses": list(TENSES),
            "models": {k: QWEN_MODELS[k] for k in model_keys},
            "temperature": temperature,
            "samples_per_cell": samples_per_cell,
            "cefr_level": None,
            "sentence_length": None,
            "output_format": "plain_text",
            "gold_source": "verbecc (+ manifest gold_participle where present)",
            "by_model": {},
        }
    else:
        payload["models"] = {
            **payload.get("models", {}),
            **{k: QWEN_MODELS[k] for k in model_keys},
        }

    for key in model_keys:
        model_id = QWEN_MODELS[key]
        print(f"\n=== {variant} / {key} ({model_id}) ===")
        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.id}...", flush=True)
            t_case = time.perf_counter()
            raw = complete(model_id, case, temperature=temperature)
            scored = score_sentence(case, raw)
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
        payload["summary"] = summarize(payload, d2a_index_by_model=d2a_index_by_model)
        _save_payload(payload, output_path)
        print(f"  checkpoint saved → {output_path}", flush=True)
        unload_model(model_id)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{DIAGNOSTIC_SERIES_LABEL} — Qwen ladder sentence probe from manifest.",
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
        default="diagnostic_3a",
        help="Diagnostic 3 variant (default: diagnostic_3a).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(DEFAULT_MODEL_KEYS),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--samples-per-cell",
        type=int,
        default=1,
        help="Sentences per cell (3A uses 1).",
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
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    variant = normalize_variant(args.variant)
    manifest_rows = load_manifest(args.manifest)
    cases = build_cases(manifest_rows, variant=variant, limit=args.limit)

    if args.dry_run:
        print(f"{DIAGNOSTIC_SERIES_LABEL}")
        print(f"Variant: {variant}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} Spanish verbs)")
        print(f"Probes: {len(cases)} ({len(manifest_rows)} verbs × 31 cells)")
        print(f"System: {system_message(variant)!r}")
        for case in cases[:6]:
            print(f"\n--- {case.id} → {case.expected_form} ---")
            print(case.prompt)
        if len(cases) > 6:
            print(f"\n... and {len(cases) - 6} more")
        return

    output_path = args.output or DEFAULT_OUTPUTS[variant]
    data = run_spike(
        cases,
        args.models,
        variant=variant,
        temperature=args.temperature,
        samples_per_cell=args.samples_per_cell,
        manifest_path=args.manifest,
        manifest_rows=manifest_rows,
        output_path=output_path,
        d2a_results_path=args.d2a_results,
        resume=args.resume,
    )
    print(f"\n--- Summary ({variant}) ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"Full results: {output_path}")


if __name__ == "__main__":
    main()
