#!/usr/bin/env python3
"""Diagnostic 2 — Spanish paradigm isolation (frequency-validated, verbecc gold).

Census-grounded version of Experiment 3: full six-person paradigms and
single-slot form asks on Spanish verbs from the Diagnostic 1 manifest
(default: all 150 Spanish verbs, 25 per frequency×irregularity cell).

Six tenses: five indicative paradigms plus past participle (single form,
matching Diagnostic 1A/B).

Part of the **Diagnostics** track; see ``research/diagnostics/registry.yaml``.

Output:
  docs/spike-results/eval_diagnostic_2_n150_paradigm_qwen_results.json
  docs/spike-results/eval_diagnostic_2_n150_single_slot_qwen_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Run:
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike --dry-run
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \\
      --probe-mode full_paradigm --models qwen17b --limit 2
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \\
      --probe-mode both --resume

Manifest: research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_2_paradigm_n150.csv
Models:    Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B (thinking disabled)
Decoding:  Greedy (temperature=0); max_new_tokens 256 (paradigm) / 64 (single slot / participle)
----------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import json
import math
import re
import string
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.lexicon.frequency import _actual_es_form, _conjugate_es, _strip_pronoun
from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking, unload_model

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"

QWEN_MODELS: dict[str, str] = {
    "qwen06b": "Qwen/Qwen3-0.6B",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B",
}

DEFAULT_MODEL_KEYS: tuple[str, ...] = ("qwen06b", "qwen17b", "qwen4b")

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_2_paradigm_n150.csv"
)

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "spike-results"

DEFAULT_OUTPUTS: dict[str, Path] = {
    "full_paradigm": RESULTS_DIR / "eval_diagnostic_2_n150_paradigm_qwen_results.json",
    "single_slot": RESULTS_DIR / "eval_diagnostic_2_n150_single_slot_qwen_results.json",
}

DIAGNOSTIC_ID = "diagnostic_2"
DIAGNOSTIC_NUMBER = "2"
DIAGNOSTIC_TITLE = "Spanish paradigm recall vs sentence binding"
DIAGNOSTIC_LABEL = "Diagnostic 2 — Spanish paradigm isolation (frequency-validated)"

ProbeMode = Literal["full_paradigm", "single_slot"]
PROBE_MODES: tuple[ProbeMode, ...] = ("full_paradigm", "single_slot")

INDICATIVE_TENSES: tuple[str, ...] = (
    "present", "preterite", "imperfect", "future", "conditional",
)
PARTICIPLE_TENSE = "participle"
TENSES: tuple[str, ...] = (*INDICATIVE_TENSES, PARTICIPLE_TENSE)

TENSE_PHRASE: dict[str, str] = {
    "present": "present indicative",
    "preterite": "preterite (pretérito indefinido) indicative",
    "imperfect": "imperfect indicative",
    "future": "simple future indicative",
    "conditional": "conditional indicative",
}

PARTICIPLE_FORM_LABEL = "past participle (participio pasado)"

PERSON_LABELS = ("yo", "tú", "él", "nosotros", "vosotros", "ellos")

PERSON_NUMBER_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("1st", "singular", "yo"),
    ("2nd", "singular", "tú"),
    ("3rd", "singular", "él"),
    ("1st", "plural", "nosotros"),
    ("2nd", "plural", "vosotros"),
    ("3rd", "plural", "ellos"),
)

SUBJECT_HINTS: dict[tuple[str, str], str] = {
    ("1st", "singular"): "yo",
    ("2nd", "singular"): "tú",
    ("3rd", "singular"): "él/ella",
    ("1st", "plural"): "nosotros/nosotras",
    ("2nd", "plural"): "vosotros/vosotras",
    ("3rd", "plural"): "ellos/ellas",
}

CELLS = (
    "high_regular", "high_irregular",
    "mid_regular", "mid_irregular",
    "low_regular", "low_irregular",
)

SYSTEM_MESSAGE = (
    "You are a Spanish conjugation assistant. "
    "Follow the instruction exactly and output only the requested verb forms."
)


@dataclass
class ParadigmCase:
    id: str
    probe_mode: ProbeMode
    lemma: str
    cell_id: str
    zipf: float
    tier: str
    irregular_probed: bool
    tense: str
    expected: list[str]
    person_labels: list[str]
    prompt: str
    is_participle: bool = False


@dataclass
class SingleSlotCase:
    id: str
    probe_mode: ProbeMode
    lemma: str
    cell_id: str
    zipf: float
    tier: str
    irregular_probed: bool
    tense: str
    person: str
    number: str
    person_label: str
    expected: str
    prompt: str
    is_participle: bool = False


ProbeCase = ParadigmCase | SingleSlotCase


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1"}


def _preterite_cell_ok(form: str, person: str, number: str) -> bool:
    """Reject verbecc preterite 1sg cells that look like imperfect (-ía)."""
    if person == "1st" and number == "singular" and form.endswith("ía"):
        return False
    return True


def gold_form(verb: str, tense: str, person: str, number: str) -> str:
    form = _actual_es_form(verb, tense, person, number)
    if form is None:
        raise RuntimeError(f"verbecc missing {verb!r} {tense} {person} {number}")
    if tense == "preterite" and not _preterite_cell_ok(form, person, number):
        raise RuntimeError(
            f"verbecc preterite bug for {verb!r} {person} {number}: {form!r}"
        )
    return form


def gold_participle_verbecc(verb: str) -> str:
    data = _conjugate_es(verb)
    if data is None:
        raise RuntimeError(f"verbecc missing participle for {verb!r}")
    entries = data["moods"].get("participo", {}).get("participo", [])
    for entry in entries:
        chunks = entry.get("c", [])
        if chunks:
            return _strip_pronoun(chunks[0])
    raise RuntimeError(f"verbecc missing participle for {verb!r}")


def gold_participle(row: dict[str, str]) -> str:
    primary = row.get("gold_participle", "").strip()
    if primary:
        return primary
    return gold_participle_verbecc(row["verb"])


def gold_paradigm(verb: str, tense: str) -> tuple[list[str], list[str]]:
    forms: list[str] = []
    labels: list[str] = []
    for person, number, label in PERSON_NUMBER_SLOTS:
        forms.append(gold_form(verb, tense, person, number))
        labels.append(label)
    return forms, labels


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    es_rows = [r for r in rows if r["lang"] == "es"]
    if not es_rows:
        raise ValueError(f"No Spanish verbs in manifest {path}")
    return es_rows


def build_full_paradigm_prompt(lemma: str, tense: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    return (
        f'Conjugate the Spanish verb "{lemma}" in the {tense_label}.\n'
        "List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.\n"
        "Reply with only the six conjugated verb forms, one per line."
    )


def build_participle_prompt_d1(lemma: str) -> str:
    """Match Diagnostic 1A wording for direct comparability."""
    return (
        f'What is the {PARTICIPLE_FORM_LABEL} of the Spanish verb "{lemma}"? '
        "Reply with one word only."
    )


def build_single_slot_prompt(lemma: str, tense: str, person: str, number: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    subject_hint = SUBJECT_HINTS[(person, number)]
    return (
        f'Conjugate the Spanish verb "{lemma}" in the {tense_label}.\n'
        f"Give the form for ({person} person, {number}) — this is the {subject_hint} form.\n"
        "Reply with only that one conjugated verb — one word, no sentence."
    )


def build_single_slot_participle_prompt(lemma: str) -> str:
    return (
        f'Give the participio pasado of the Spanish verb "{lemma}".\n'
        "Reply with only that one conjugated verb — one word, no sentence."
    )


def build_cases(
    manifest_rows: list[dict[str, str]],
    *,
    probe_mode: ProbeMode,
    limit: int | None = None,
) -> list[ProbeCase]:
    cases: list[ProbeCase] = []

    for row in manifest_rows:
        lemma = row["verb"]
        participle = gold_participle(row)
        base = {
            "lemma": lemma,
            "cell_id": row["cell_id"],
            "zipf": float(row["zipf"]),
            "tier": row["tier"],
            "irregular_probed": _parse_bool(row["irregular_probed"]),
        }

        if probe_mode == "full_paradigm":
            for tense in INDICATIVE_TENSES:
                expected, labels = gold_paradigm(lemma, tense)
                cases.append(
                    ParadigmCase(
                        id=f"{lemma}__{tense}",
                        probe_mode=probe_mode,
                        tense=tense,
                        expected=expected,
                        person_labels=labels,
                        prompt=build_full_paradigm_prompt(lemma, tense),
                        **base,
                    )
                )
            cases.append(
                ParadigmCase(
                    id=f"{lemma}__{PARTICIPLE_TENSE}",
                    probe_mode=probe_mode,
                    tense=PARTICIPLE_TENSE,
                    expected=[participle],
                    person_labels=["participle"],
                    prompt=build_participle_prompt_d1(lemma),
                    is_participle=True,
                    **base,
                )
            )
        else:
            for tense in INDICATIVE_TENSES:
                for person, number, label in PERSON_NUMBER_SLOTS:
                    expected = gold_form(lemma, tense, person, number)
                    cases.append(
                        SingleSlotCase(
                            id=f"{lemma}__{tense}__{person}_{number}",
                            probe_mode=probe_mode,
                            tense=tense,
                            person=person,
                            number=number,
                            person_label=label,
                            expected=expected,
                            prompt=build_single_slot_prompt(lemma, tense, person, number),
                            **base,
                        )
                    )
            cases.append(
                SingleSlotCase(
                    id=f"{lemma}__{PARTICIPLE_TENSE}",
                    probe_mode=probe_mode,
                    tense=PARTICIPLE_TENSE,
                    person="",
                    number="",
                    person_label="participle",
                    expected=participle,
                    prompt=build_single_slot_participle_prompt(lemma),
                    is_participle=True,
                    **base,
                )
            )

    if limit is not None:
        cases = cases[:limit]
    return cases


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip(_EDGE_PUNCT).casefold()


def _tokenize_spanish(text: str) -> list[str]:
    text = _strip_thinking(text)
    return re.findall(r"[\w\u00C0-\u024F]+", text, flags=re.UNICODE)


def _first_token(text: str) -> str:
    cleaned = _strip_thinking(text).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response|respuesta)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    match = re.search(r"[\w'\-]+", cleaned, flags=re.UNICODE)
    return match.group(0) if match else cleaned


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _max_new_tokens(case: ProbeCase) -> int:
    if isinstance(case, SingleSlotCase) or case.is_participle:
        return 64
    return 256


def complete(
    model_id: str,
    case: ProbeCase,
    *,
    temperature: float,
) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": case.prompt},
    ]
    template_kwargs: dict[str, Any] = {"add_generation_prompt": True, "tokenize": False}
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": _max_new_tokens(case),
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


def score_paradigm(case: ParadigmCase, raw: str) -> dict[str, Any]:
    if case.is_participle:
        return _score_strict_single_form(case, raw)

    tokens = [_normalize(t) for t in _tokenize_spanish(raw)]
    token_set = set(tokens)
    per_person: list[dict[str, Any]] = []
    hits = 0
    line_hits = 0
    lines = [ln.strip() for ln in _strip_thinking(raw).splitlines() if ln.strip()]

    for i, (label, gold) in enumerate(zip(case.person_labels, case.expected, strict=True)):
        gold_norm = _normalize(gold)
        found = gold_norm in token_set
        if found:
            hits += 1
        line_found = False
        if i < len(lines):
            line_token = _first_token(lines[i])
            line_found = _normalize(line_token) == gold_norm
            if line_found:
                line_hits += 1
        per_person.append(
            {
                "person": label,
                "expected": gold,
                "found": found,
                "line_order_match": line_found,
            }
        )

    return {
        "raw": raw.strip(),
        "forms_found": hits,
        "forms_total": len(case.expected),
        "form_recall": round(hits / len(case.expected), 4),
        "line_order_recall": round(line_hits / len(case.expected), 4),
        "per_person": per_person,
        "missing": [p["expected"] for p in per_person if not p["found"]],
        "correct": hits == len(case.expected),
    }


def _score_strict_single_form(case: ProbeCase, raw: str) -> dict[str, Any]:
    token = _first_token(raw)
    norm = _normalize(token)
    if isinstance(case, ParadigmCase):
        expected = case.expected[0]
    else:
        expected = case.expected
    expected_norm = _normalize(expected)
    correct = norm == expected_norm
    return {
        "raw": raw.strip(),
        "parsed_token": token,
        "forms_found": 1 if correct else 0,
        "forms_total": 1,
        "form_recall": 1.0 if correct else 0.0,
        "correct": correct,
        "infinitive_fallback": norm == _normalize(case.lemma),
    }


def score_single_slot(case: SingleSlotCase, raw: str) -> dict[str, Any]:
    scored = _score_strict_single_form(case, raw)
    return {
        "raw": scored["raw"],
        "parsed_token": scored["parsed_token"],
        "correct": scored["correct"],
        "infinitive_fallback": scored["infinitive_fallback"],
    }


def _rate_paradigm(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows
        if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n_forms = sum(r["forms_total"] for r in filtered)
    k_forms = sum(r["forms_found"] for r in filtered)
    lo, hi = wilson_ci(k_forms, n_forms)
    n_cases = len(filtered)
    return {
        "cases": n_cases,
        "forms_correct": k_forms,
        "forms_total": n_forms,
        "form_recall": round(k_forms / n_forms, 4) if n_forms else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
        "mean_recall_per_case": round(
            sum(r["form_recall"] for r in filtered) / n_cases, 4
        )
        if n_cases
        else None,
    }


def _rate_single_slot(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows
        if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n = len(filtered)
    k = sum(1 for r in filtered if r["correct"])
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    probe_mode: ProbeMode = payload["probe_mode"]
    out: dict[str, Any] = {"per_model": {}}

    for key, block in payload["by_model"].items():
        rows = block["results"]
        per_model: dict[str, Any] = {}

        if probe_mode == "full_paradigm":
            per_model["overall"] = _rate_paradigm(rows)
            for cell in CELLS:
                per_model[cell] = _rate_paradigm(rows, cell_id=cell)
            for tense in TENSES:
                per_model[f"tense_{tense}"] = _rate_paradigm(rows, tense=tense)
            per_model["failures"] = [
                {
                    "id": r["case"]["id"],
                    "cell_id": r["case"]["cell_id"],
                    "tense": r["case"]["tense"],
                    "missing": r.get("missing", []),
                    "form_recall": r["form_recall"],
                    "got": r.get("parsed_token"),
                }
                for r in rows
                if r["form_recall"] < 1.0
            ]
        else:
            per_model["overall"] = _rate_single_slot(rows)
            for cell in CELLS:
                per_model[cell] = _rate_single_slot(rows, cell_id=cell)
            for tense in TENSES:
                per_model[f"tense_{tense}"] = _rate_single_slot(rows, tense=tense)
            per_model["failures"] = [
                {
                    "id": r["case"]["id"],
                    "cell_id": r["case"]["cell_id"],
                    "tense": r["case"]["tense"],
                    "expected": r["case"]["expected"],
                    "got": r["parsed_token"],
                }
                for r in rows
                if not r["correct"]
            ]

        out["per_model"][key] = per_model
    return out


def _save_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _score_case(case: ProbeCase, raw: str) -> dict[str, Any]:
    if isinstance(case, ParadigmCase):
        return score_paradigm(case, raw)
    return score_single_slot(case, raw)


def run_spike(
    cases: list[ProbeCase],
    model_keys: list[str],
    *,
    probe_mode: ProbeMode,
    temperature: float,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if resume and output_path.is_file():
        with output_path.open(encoding="utf-8") as f:
            payload = json.load(f)
        done = set(payload.get("by_model", {}))
        model_keys = [k for k in model_keys if k not in done]
        if not model_keys:
            print(f"All requested models already in {output_path}", flush=True)
            return payload
        print(f"Resuming {probe_mode}; remaining models: {model_keys}", flush=True)

    if payload is None:
        payload = {
            "diagnostic_id": DIAGNOSTIC_ID,
            "diagnostic_number": DIAGNOSTIC_NUMBER,
            "diagnostic_title": DIAGNOSTIC_TITLE,
            "diagnostic_label": DIAGNOSTIC_LABEL,
            "related_diagnostics": ["diagnostic_1a", "diagnostic_1b"],
            "related_experiments": [3, "3B", 10],
            "probe_mode": probe_mode,
            "prompt_version": "explicit_v1",
            "manifest_path": str(manifest_path),
            "manifest_seed": manifest_rows[0].get("seed") if manifest_rows else None,
            "n_verbs": len(manifest_rows),
            "n_probes": len(cases),
            "indicative_tenses": list(INDICATIVE_TENSES),
            "tenses": list(TENSES),
            "models": {k: QWEN_MODELS[k] for k in model_keys},
            "temperature": temperature,
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
        print(f"\n=== {probe_mode} / {key} ({model_id}) ===")
        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.id}...", flush=True)
            t_case = time.perf_counter()
            raw = complete(model_id, case, temperature=temperature)
            scored = _score_case(case, raw)
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
        payload["summary"] = summarize(payload)
        _save_payload(payload, output_path)
        print(f"  checkpoint saved → {output_path}", flush=True)
        unload_model(model_id)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{DIAGNOSTIC_LABEL} — Qwen ladder paradigm probe from manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Verb manifest CSV (default: manifest_diagnostic_2_paradigm_n150.csv).",
    )
    parser.add_argument(
        "--probe-mode",
        choices=("full_paradigm", "single_slot", "both"),
        default="both",
        help="Which probe mode(s) to run (default: both).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(DEFAULT_MODEL_KEYS),
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=None, help="First N probes only.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None, help="Override output JSON path.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    manifest_rows = load_manifest(args.manifest)
    modes: list[ProbeMode]
    if args.probe_mode == "both":
        modes = list(PROBE_MODES)
    else:
        modes = [args.probe_mode]  # type: ignore[list-item]

    if args.dry_run:
        print(f"{DIAGNOSTIC_LABEL}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} Spanish verbs)")
        for mode in modes:
            cases = build_cases(manifest_rows, probe_mode=mode, limit=args.limit)
            print(f"\n[{mode}] {len(cases)} probes")
            for c in cases[:12]:
                if isinstance(c, ParadigmCase):
                    print(f"  [{c.cell_id}/{c.tense}] {c.lemma} -> {c.expected}")
                else:
                    print(
                        f"  [{c.cell_id}/{c.tense}/{c.person_label}] "
                        f"{c.lemma} -> {c.expected}"
                    )
            if len(cases) > 12:
                print(f"  ... and {len(cases) - 12} more")
        return

    for mode in modes:
        cases = build_cases(manifest_rows, probe_mode=mode, limit=args.limit)
        output_path = args.output or DEFAULT_OUTPUTS[mode]
        if args.probe_mode == "both":
            output_path = DEFAULT_OUTPUTS[mode]
        data = run_spike(
            cases,
            args.models,
            probe_mode=mode,
            temperature=args.temperature,
            manifest_path=args.manifest,
            manifest_rows=manifest_rows,
            output_path=output_path,
            resume=args.resume,
        )
        print(f"\n--- Summary ({mode}) ---")
        print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
        print(f"Full results: {output_path}")


if __name__ == "__main__":
    main()
