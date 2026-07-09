#!/usr/bin/env python3
"""Diagnostic 3 — Spanish sentence binding (frequency-validated, verbecc gold).

Paired sentence probes on the same 150 Spanish verbs as Diagnostic 2A:

- **Diagnostic 3A** (``diagnostic_3a``): plain-text sentence, 2A-aligned tense/person
  hints, no length band, no JSON, no CEFR — compare slot-level pass to 2A strict.
- **Diagnostic 3B** (``diagnostic_3b``): production ``build_prompt`` JSON (short,
  translation field) **plus 3A-style subject/tense hints**; T=0, 1 sample/cell.
- **Diagnostic 3C** (``diagnostic_3c``): production ``build_prompt`` baseline (short,
  JSON + translation, generic constraint labels, no CEFR), T=0, 1 sample/cell.
- **Diagnostic 3D** (``diagnostic_3d``): same prompt as 3C, T=0.7, 10 samples/cell
  (pass@10), batched JSON with top-up retries on parse failure (mirrors
  ``baseline_hf``); default model is 1.7B only.

Part of the **Diagnostics** track; see ``research/diagnostics/registry.yaml``.

Output:
  docs/spike-results/eval_diagnostic_3a_n150_sentence_qwen_results.json
  docs/spike-results/eval_diagnostic_3b_n150_sentence_qwen_results.json
  docs/spike-results/eval_diagnostic_3c_n150_sentence_qwen_results.json
  docs/spike-results/eval_diagnostic_3d_n150_sentence_qwen_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Run:
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike --dry-run
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3a --models qwen17b --limit 5
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3b --resume
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3c --resume
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \\
      --variant diagnostic_3d --resume

Manifest: research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv
Models:    Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B (3D default: 1.7B only)
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.length_bands import band_label
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    ChatGenerationSpec,
    DEFAULT_HF_BATCH_SIZE,
    generate_chat_batch,
    parse_candidates_lenient,
    unload_model,
)
from research.generation.prompt_builder import build_prompt
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

Variant = Literal[
    "diagnostic_3a", "diagnostic_3b", "diagnostic_3c", "diagnostic_3d"
]
VARIANTS: tuple[Variant, ...] = (
    "diagnostic_3a",
    "diagnostic_3b",
    "diagnostic_3c",
    "diagnostic_3d",
)
PRODUCTION_VARIANTS: tuple[Variant, ...] = (
    "diagnostic_3b",
    "diagnostic_3c",
    "diagnostic_3d",
)

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "spike-results"

DEFAULT_OUTPUTS: dict[Variant, Path] = {
    "diagnostic_3a": RESULTS_DIR / "eval_diagnostic_3a_n150_sentence_qwen_results.json",
    "diagnostic_3b": RESULTS_DIR / "eval_diagnostic_3b_n150_sentence_qwen_results.json",
    "diagnostic_3c": RESULTS_DIR / "eval_diagnostic_3c_n150_sentence_qwen_results.json",
    "diagnostic_3d": RESULTS_DIR / "eval_diagnostic_3d_n150_sentence_qwen_results.json",
}

DEFAULT_2A_RESULTS = RESULTS_DIR / "eval_diagnostic_2a_n150_paradigm_qwen_results.json"

DIAGNOSTIC_SERIES = "diagnostic_3"
DIAGNOSTIC_SERIES_TITLE = "Spanish sentence binding vs paradigm recall"
DIAGNOSTIC_SERIES_LABEL = "Diagnostic 3 — Spanish sentence binding (frequency-validated)"

VARIANT_META: dict[Variant, dict[str, Any]] = {
    "diagnostic_3a": {
        "diagnostic_id": "diagnostic_3a",
        "diagnostic_number": "3A",
        "diagnostic_title": "Spanish sentence binding (2A-aligned hints, plain text)",
        "diagnostic_label": "Diagnostic 3A — Spanish sentence binding (plain text)",
        "prompt_version": "sentence_3a_v1",
        "temperature": 0.0,
        "samples_per_cell": 1,
        "default_models": DEFAULT_MODEL_KEYS,
        "sentence_length": None,
        "output_format": "plain_text",
        "cefr_level": None,
    },
    "diagnostic_3b": {
        "diagnostic_id": "diagnostic_3b",
        "diagnostic_number": "3B",
        "diagnostic_title": "Spanish sentence binding (production JSON + 3A hints)",
        "diagnostic_label": "Diagnostic 3B — Spanish sentence binding (JSON + hints)",
        "prompt_version": "build_prompt_baseline_hints_v1",
        "temperature": 0.0,
        "samples_per_cell": 1,
        "default_models": DEFAULT_MODEL_KEYS,
        "sentence_length": "short",
        "output_format": "json",
        "subject_hints": True,
        "cefr_level": None,
    },
    "diagnostic_3c": {
        "diagnostic_id": "diagnostic_3c",
        "diagnostic_number": "3C",
        "diagnostic_title": "Spanish sentence binding (production baseline prompt)",
        "diagnostic_label": "Diagnostic 3C — Spanish sentence binding (production prompt)",
        "prompt_version": "build_prompt_baseline_v1",
        "temperature": 0.0,
        "samples_per_cell": 1,
        "default_models": DEFAULT_MODEL_KEYS,
        "sentence_length": "short",
        "output_format": "json",
        "subject_hints": False,
        "cefr_level": None,
    },
    "diagnostic_3d": {
        "diagnostic_id": "diagnostic_3d",
        "diagnostic_number": "3D",
        "diagnostic_title": "Spanish sentence binding (production prompt, stochastic)",
        "diagnostic_label": "Diagnostic 3D — Spanish sentence binding (T=0.7, pass@10)",
        "prompt_version": "build_prompt_baseline_v1",
        "temperature": 0.7,
        "samples_per_cell": 10,
        "default_models": ("qwen17b",),
        "sentence_length": "short",
        "output_format": "json",
        "subject_hints": False,
        "cefr_level": None,
    },
}

SYSTEM_MESSAGE_3A = (
    "You are a Spanish language assistant. Follow the instruction exactly."
)
SYSTEM_MESSAGE_PRODUCTION = (
    "You are a helpful Spanish language tutor. Always respond with valid JSON."
)

_JSONish_RE = re.compile(r"^\s*[\[{]")
_EF = ExpectedFormMatchEvaluator()
MAX_TOPUP_CALLS = BaselineHFGenerator.MAX_CALLS


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


def lemma_translation(lemma: str) -> str:
    """Manifest verbs lack English glosses; use lemma as a neutral placeholder."""
    return lemma


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


def _morphology_hint_overlay_3a(
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
) -> str:
    """Same subject/tense hint wording as Diagnostic 3A, appended to production JSON prompts."""
    tense_label = TENSE_PHRASE.get(tense, tense)
    subject_hint = SUBJECT_HINTS[(person, number)]
    return (
        f'The verb "{lemma}" must appear inflected in the {tense_label} '
        f"for {subject_hint} ({person} person, {number}) — "
        "not as the bare infinitive.\n"
    )


def build_prompt_production_participle(
    lemma: str,
    *,
    participle: str,
    num_candidates: int,
    sentence_length: str,
) -> str:
    """Production-style JSON prompt for participle cells (not covered by build_prompt)."""
    length_desc = band_label(sentence_length)
    translation = lemma_translation(lemma)
    return (
        "You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word (lemma): "{lemma}" (English: "{translation}")\n'
        f"Constraints:\n  length: {length_desc}.\n"
        f'The sentence must contain the past participle of "{lemma}" '
        f'(the form "{participle}") — not the bare infinitive.\n'
        f"Produce {num_candidates} natural Spanish sentences within the length band. "
        "Each sentence must contain the participle form specified above, "
        "with its English translation.\n"
        "Reply ONLY as JSON in this exact shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


# Back-compat alias for Diagnostic 4 (baseline scaffold = production, no hints).
build_prompt_3c_participle = build_prompt_production_participle


def build_prompt_production_indicative(
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    num_candidates: int,
    sentence_length: str,
    with_hints: bool = False,
) -> str:
    prompt = build_prompt(
        keyword=lemma,
        translation=lemma_translation(lemma),
        target_language="es",
        constraints={"tense": tense, "person": person, "number": number},
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=None,
    )
    if with_hints:
        prompt += "\n" + _morphology_hint_overlay_3a(
            lemma, tense=tense, person=person, number=number
        )
    return prompt


# Back-compat alias for Diagnostic 4 (baseline scaffold = production, no hints).
build_prompt_3c_indicative = build_prompt_production_indicative


def build_case_prompt(
    variant: Variant,
    lemma: str,
    *,
    tense: str,
    person: str,
    number: str,
    expected_form: str,
    is_participle: bool,
    num_candidates: int,
) -> str:
    if variant == "diagnostic_3a":
        return build_prompt_3a(
            lemma,
            tense=tense,
            person=person,
            number=number,
            expected_form=expected_form,
            is_participle=is_participle,
        )

    sentence_length = str(variant_config(variant)["sentence_length"])
    with_hints = bool(variant_config(variant).get("subject_hints"))
    if is_participle:
        return build_prompt_production_participle(
            lemma,
            participle=expected_form,
            num_candidates=num_candidates,
            sentence_length=sentence_length,
        )
    return build_prompt_production_indicative(
        lemma,
        tense=tense,
        person=person,
        number=number,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        with_hints=with_hints,
    )


def build_prompt_for_case(case: SentenceCase) -> str:
    return case.prompt


def system_message(variant: Variant) -> str:
    if variant == "diagnostic_3a":
        return SYSTEM_MESSAGE_3A
    return SYSTEM_MESSAGE_PRODUCTION


def build_cases(
    manifest_rows: list[dict[str, str]],
    *,
    variant: Variant,
    num_candidates: int,
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
            "num_candidates": num_candidates,
        }

        for tense in INDICATIVE_TENSES:
            for person, number, label in PERSON_NUMBER_SLOTS:
                expected = gold_form(lemma, tense, person, number)
                prompt = build_case_prompt(
                    variant,
                    lemma,
                    tense=tense,
                    person=person,
                    number=number,
                    expected_form=expected,
                    is_participle=False,
                    num_candidates=num_candidates,
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
                        constraints={"tense": tense, "person": person, "number": number},
                        **base,
                    )
                )

        prompt = build_case_prompt(
            variant,
            lemma,
            tense=PARTICIPLE_TENSE,
            person="",
            number="",
            expected_form=participle,
            is_participle=True,
            num_candidates=num_candidates,
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
                constraints={},
                **base,
            )
        )

    if limit is not None:
        cases = cases[:limit]
    return cases


def extract_plain_sentence(raw: str) -> str:
    """Take the first usable sentence line from plain model output."""
    cleaned = _strip_thinking(raw).strip()
    if not cleaned:
        return ""

    if _JSONish_RE.match(cleaned):
        cands, _ = parse_candidates_lenient(cleaned)
        if cands:
            return str(cands[0].get("sentence", "")).strip()

    for line in cleaned.splitlines():
        line = line.strip().strip('"').strip("'")
        if line:
            return line
    return cleaned


def _score_one_sentence(sentence: str, expected_form: str) -> dict[str, Any]:
    ef = _EF.evaluate(sentence, "", {"expected_form": expected_form})
    passed = bool(ef.details.get("passed"))
    return {
        "sentence": sentence,
        "expected_form_pass": passed,
        "matched_token": ef.details.get("matched_token"),
        "tokens_checked": ef.details.get("tokens_checked"),
    }


def _score_json_candidates(
    case: SentenceCase,
    cands: list[dict[str, str]],
    *,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    scored_cands: list[dict[str, Any]] = []
    for cand in cands:
        sentence = str(cand.get("sentence", "")).strip()
        translation = str(cand.get("translation", "")).strip()
        one = _score_one_sentence(sentence, case.expected_form)
        scored_cands.append(
            {
                "sentence": sentence,
                "translation": translation,
                **one,
            }
        )

    n_pass = sum(1 for c in scored_cands if c["expected_form_pass"])
    pass_at_k = n_pass > 0
    first = scored_cands[0] if scored_cands else None
    out: dict[str, Any] = {
        "candidates": scored_cands,
        "n_candidates_parsed": len(scored_cands),
        "n_pass": n_pass,
        "pass_at_k": pass_at_k,
        "pass_at_1": bool(first and first["expected_form_pass"]),
        "sentence": first["sentence"] if first else "",
        "translation": first["translation"] if first else "",
        "expected_form_pass": pass_at_k if case.num_candidates > 1 else bool(
            first and first["expected_form_pass"]
        ),
        "matched_token": first["matched_token"] if first else None,
        "tokens_checked": first["tokens_checked"] if first else 0,
    }
    if parse_mode is not None:
        out["parse_mode"] = parse_mode
    return out


def score_output(case: SentenceCase, raw: str) -> dict[str, Any]:
    cfg = variant_config(case.variant)
    output_format = cfg["output_format"]

    if output_format == "plain_text":
        sentence = extract_plain_sentence(raw)
        scored = _score_one_sentence(sentence, case.expected_form)
        return {
            "raw": raw.strip(),
            **scored,
        }

    cands, parse_mode = parse_candidates_lenient(_strip_thinking(raw))
    return {
        "raw": raw.strip(),
        **_score_json_candidates(case, cands, parse_mode=parse_mode),
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


def _rate(rows: list[dict[str, Any]], *, pass_key: str = "expected_form_pass", **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows
        if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n = len(filtered)
    k = sum(1 for r in filtered if r.get(pass_key))
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def _binding_gap(
    rows: list[dict[str, Any]],
    d2a_index: dict[str, bool],
    *,
    pass_key: str = "expected_form_pass",
) -> dict[str, Any]:
    known = 0
    known_sentence_pass = 0
    gap = 0
    for row in rows:
        case_id = row["case"]["id"]
        if not d2a_index.get(case_id):
            continue
        known += 1
        if row.get(pass_key):
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
    variant = payload.get("variant", "diagnostic_3a")
    samples_per_cell = int(payload.get("samples_per_cell", 1))
    pass_key = "expected_form_pass"
    out: dict[str, Any] = {"per_model": {}}

    for key, block in payload.get("by_model", {}).items():
        rows = block["results"]
        per_model: dict[str, Any] = {
            "overall": _rate(rows, pass_key=pass_key),
        }
        if samples_per_cell > 1:
            per_model["pass_at_1"] = _rate(rows, pass_key="pass_at_1")
            per_model["pass_at_k"] = _rate(rows, pass_key="pass_at_k")

        for tier in ("high", "mid", "low"):
            per_model[f"tier_{tier}"] = _rate(rows, pass_key=pass_key, tier=tier)
        for tense in TENSES:
            per_model[f"tense_{tense}"] = _rate(rows, pass_key=pass_key, tense=tense)

        d2a_index = d2a_index_by_model.get(key, {})
        if d2a_index:
            per_model["binding_gap_vs_2a_strict"] = _binding_gap(rows, d2a_index, pass_key=pass_key)
            for tier in ("high", "mid", "low"):
                tier_rows = [r for r in rows if r["case"].get("tier") == tier]
                per_model[f"binding_gap_tier_{tier}"] = _binding_gap(
                    tier_rows, d2a_index, pass_key=pass_key
                )

        per_model["failures"] = [
            {
                "id": r["case"]["id"],
                "lemma": r["case"]["lemma"],
                "tense": r["case"]["tense"],
                "expected_form": r["case"]["expected_form"],
                "sentence": r.get("sentence"),
                "n_pass": r.get("n_pass"),
                "raw": r.get("raw"),
            }
            for r in rows
            if not r.get(pass_key)
        ]
        out["per_model"][key] = per_model
    out["variant"] = variant
    return out


def _max_new_tokens_for_candidates(num_candidates: int, *, variant: Variant) -> int:
    if variant == "diagnostic_3a":
        return 128
    return min(80 * num_candidates + 200, 3072)


def _prompt_for_remaining(case: SentenceCase, remaining: int) -> str:
    if remaining == case.num_candidates and case.prompt:
        return case.prompt
    return build_case_prompt(
        case.variant,
        case.lemma,
        tense=case.tense,
        person=case.person,
        number=case.number,
        expected_form=case.expected_form,
        is_participle=case.is_participle,
        num_candidates=remaining,
    )


def _generation_spec(case: SentenceCase, *, prompt: str, max_new_tokens: int) -> ChatGenerationSpec:
    return ChatGenerationSpec(
        system=system_message(case.variant),
        user=prompt,
        max_new_tokens=max_new_tokens,
    )


def complete(model_id: str, case: SentenceCase, *, temperature: float) -> str:
    prompt = build_prompt_for_case(case)
    return generate_chat_batch(
        model_id,
        [
            _generation_spec(
                case,
                prompt=prompt,
                max_new_tokens=_max_new_tokens_for_candidates(
                    case.num_candidates,
                    variant=case.variant,
                ),
            )
        ],
        temperature=temperature,
        batch_size=1,
    )[0]


def _complete_cases_batched(
    model_id: str,
    cases: list[SentenceCase],
    *,
    temperature: float,
    batch_size: int,
) -> list[str]:
    specs = [
        _generation_spec(
            case,
            prompt=build_prompt_for_case(case),
            max_new_tokens=_max_new_tokens_for_candidates(
                case.num_candidates,
                variant=case.variant,
            ),
        )
        for case in cases
    ]
    return generate_chat_batch(
        model_id,
        specs,
        temperature=temperature,
        batch_size=batch_size,
    )


def complete_with_topup(
    model_id: str,
    case: SentenceCase,
    *,
    temperature: float,
) -> dict[str, Any]:
    """Batched JSON generation with top-up calls when parsing returns too few candidates."""
    return _complete_with_topup_batched(
        model_id,
        [case],
        temperature=temperature,
        batch_size=1,
    )[0]


def _complete_with_topup_batched(
    model_id: str,
    cases: list[SentenceCase],
    *,
    temperature: float,
    batch_size: int,
) -> list[dict[str, Any]]:
    collected: list[list[dict[str, str]]] = [[] for _ in cases]
    raw_calls: list[list[str]] = [[] for _ in cases]
    parse_modes: list[list[str]] = [[] for _ in cases]
    active = list(range(len(cases)))

    for call_idx in range(MAX_TOPUP_CALLS):
        if not active:
            break
        specs: list[ChatGenerationSpec] = []
        for idx in active:
            case = cases[idx]
            remaining = case.num_candidates - len(collected[idx])
            prompt = _prompt_for_remaining(case, remaining)
            specs.append(
                _generation_spec(
                    case,
                    prompt=prompt,
                    max_new_tokens=_max_new_tokens_for_candidates(
                        remaining,
                        variant=case.variant,
                    ),
                )
            )

        raws = generate_chat_batch(
            model_id,
            specs,
            temperature=temperature,
            batch_size=batch_size,
        )

        next_active: list[int] = []
        for idx, raw in zip(active, raws):
            case = cases[idx]
            raw_calls[idx].append(raw.strip())
            cands, mode = parse_candidates_lenient(raw)
            parse_modes[idx].append(mode)
            remaining = case.num_candidates - len(collected[idx])
            print(
                f"      [{case.id} top-up {call_idx + 1}/{MAX_TOPUP_CALLS}] "
                f"requested={remaining} parsed={len(cands)} mode={mode}",
                flush=True,
            )
            collected[idx].extend(cands)
            if (
                len(collected[idx]) < case.num_candidates
                and call_idx + 1 < MAX_TOPUP_CALLS
            ):
                next_active.append(idx)
        active = next_active

    return [
        {
            "candidates": collected[idx][: cases[idx].num_candidates],
            "raw_calls": raw_calls[idx],
            "parse_modes": parse_modes[idx],
            "n_generation_calls": len(raw_calls[idx]),
        }
        for idx in range(len(cases))
    ]


def _join_raw_calls(raw_calls: list[str]) -> str:
    if not raw_calls:
        return ""
    if len(raw_calls) == 1:
        return raw_calls[0]
    parts = [
        f"--- generation call {idx + 1} ---\n{raw.strip()}"
        for idx, raw in enumerate(raw_calls)
    ]
    return "\n\n".join(parts)


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
    batch_size: int = DEFAULT_HF_BATCH_SIZE,
) -> dict[str, Any]:
    meta = variant_config(variant)
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
            "related_diagnostics": ["diagnostic_2a", "diagnostic_3a"],
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
            "batch_size": batch_size,
            "generation_topup_calls_max": (
                MAX_TOPUP_CALLS if samples_per_cell > 1 else None
            ),
            "cefr_level": meta["cefr_level"],
            "sentence_length": meta["sentence_length"],
            "output_format": meta["output_format"],
            "gold_source": "verbecc (+ manifest gold_participle where present)",
            "by_model": {},
        }
        if variant == "diagnostic_3a":
            payload["related_diagnostics"] = ["diagnostic_2a"]
        elif variant == "diagnostic_3b":
            payload["related_diagnostics"] = ["diagnostic_2a", "diagnostic_3a"]
        elif variant == "diagnostic_3c":
            payload["related_diagnostics"] = [
                "diagnostic_2a",
                "diagnostic_3a",
                "diagnostic_3b",
            ]
        elif variant == "diagnostic_3d":
            payload["related_diagnostics"] = [
                "diagnostic_2a",
                "diagnostic_3a",
                "diagnostic_3b",
                "diagnostic_3c",
            ]
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
        use_topup = samples_per_cell > 1
        for batch_start in range(0, len(cases), batch_size):
            batch_cases = cases[batch_start : batch_start + batch_size]
            batch_end = batch_start + len(batch_cases)
            print(
                f"  [{batch_end}/{len(cases)}] batch {batch_start + 1}-{batch_end} "
                f"(size={len(batch_cases)})...",
                flush=True,
            )
            t_batch = time.perf_counter()
            if use_topup:
                batches = _complete_with_topup_batched(
                    model_id,
                    batch_cases,
                    temperature=temperature,
                    batch_size=batch_size,
                )
                for case, batch in zip(batch_cases, batches):
                    scored = _score_json_candidates(case, batch["candidates"])
                    scored["raw"] = _join_raw_calls(batch["raw_calls"])
                    scored["raw_calls"] = batch["raw_calls"]
                    scored["parse_modes"] = batch["parse_modes"]
                    scored["n_generation_calls"] = batch["n_generation_calls"]
                    rows.append(
                        {
                            "case": asdict(case),
                            "latency_s": round(
                                (time.perf_counter() - t_batch) / len(batch_cases),
                                3,
                            ),
                            **scored,
                        }
                    )
            else:
                raws = _complete_cases_batched(
                    model_id,
                    batch_cases,
                    temperature=temperature,
                    batch_size=batch_size,
                )
                batch_elapsed = time.perf_counter() - t_batch
                per_case_latency = batch_elapsed / len(batch_cases)
                for case, raw in zip(batch_cases, raws):
                    scored = score_output(case, raw)
                    rows.append(
                        {
                            "case": asdict(case),
                            "latency_s": round(per_case_latency, 3),
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
        default=None,
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_HF_BATCH_SIZE,
        help=f"Padded HF prompts per generate() call (default: {DEFAULT_HF_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--samples-per-cell",
        type=int,
        default=None,
        help="Sentences requested per cell (3A–3C: 1; 3D: 10).",
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
    cfg = variant_config(variant)
    temperature = cfg["temperature"] if args.temperature is None else args.temperature
    samples_per_cell = cfg["samples_per_cell"] if args.samples_per_cell is None else args.samples_per_cell
    model_keys = list(cfg["default_models"]) if args.models is None else args.models

    manifest_rows = load_manifest(args.manifest)
    cases = build_cases(
        manifest_rows,
        variant=variant,
        num_candidates=samples_per_cell,
        limit=args.limit,
    )

    if args.dry_run:
        print(f"{DIAGNOSTIC_SERIES_LABEL}")
        print(f"Variant: {variant}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} Spanish verbs)")
        print(f"Probes: {len(cases)} ({len(manifest_rows)} verbs × 31 cells)")
        print(f"Models: {model_keys}")
        print(f"Temperature: {temperature}")
        print(f"Samples per cell: {samples_per_cell}")
        print(f"System: {system_message(variant)!r}")
        for case in cases[:4]:
            print(f"\n--- {case.id} → {case.expected_form} ---")
            print(case.prompt)
        if len(cases) > 4:
            print(f"\n... and {len(cases) - 4} more")
        return

    output_path = args.output or DEFAULT_OUTPUTS[variant]
    data = run_spike(
        cases,
        model_keys,
        variant=variant,
        temperature=temperature,
        samples_per_cell=samples_per_cell,
        manifest_path=args.manifest,
        manifest_rows=manifest_rows,
        output_path=output_path,
        d2a_results_path=args.d2a_results,
        resume=args.resume,
        batch_size=args.batch_size,
    )
    print(f"\n--- Summary ({variant}) ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"Full results: {output_path}")


if __name__ == "__main__":
    main()
