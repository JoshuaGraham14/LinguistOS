#!/usr/bin/env python3
"""Knowledge probe vs sentence EF on spanish_basic_grid (Exp 10).

Two probe modes (``--probe-mode``):

- ``single_slot`` — one easy ask per cell (50 calls); ``explicit_single_slot_v1``
- ``full_paradigm`` — list all six forms per verb×tense (25 calls); ``explicit_v2_grid``

Joins sentence-level EF from existing DB experiments (Exp 9 baseline id=15,
optional form-injected id=16).

Usage:
    python3 -m research.prototyping.spanish_grid_knowledge_vs_sentence \\
        --probe-mode full_paradigm --models qwen17b \\
        --output docs/spike-results/eval_spanish_basic_grid_paradigm_qwen17b_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import joinedload

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.db.database import SessionLocal
from research.db.models import Benchmark, Experiment, GeneratedSentence
from research.generation.languages import extract_constraints
from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking
from research.prototyping.spanish_paradigm_qwen_spike import (
    PARADIGMS,
    QWEN_MODELS,
    TENSE_PHRASE,
    _normalize,
    _tokenize_spanish,
    score_paradigm,
    wilson_ci,
)
from research.prototyping.spanish_paradigm_qwen_spike import ParadigmCase


def complete_paradigm(model_id: str, prompt: str, *, temperature: float) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    system = (
        "You are a Spanish conjugation assistant. "
        "Follow the instruction exactly and output only the requested verb forms."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": True,
        "tokenize": False,
    }
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": 256,
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


def complete_single_slot(model_id: str, prompt: str, *, temperature: float) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    system = (
        "You are a Spanish conjugation assistant. "
        "Follow the instruction exactly and output only the requested verb form."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": True,
        "tokenize": False,
    }
    if _is_qwen3(model_id):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    gen_kwargs: dict[str, Any] = {
        "max_new_tokens": 64,
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

PROMPT_VERSIONS = {
    "single_slot": "explicit_single_slot_v1",
    "full_paradigm": "explicit_v2_grid",
}

_BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
_DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "docs/spike-results/eval_spanish_basic_grid_knowledge_qwen17b_results.json"
)

SUBJECT_HINTS: dict[tuple[str, str], str] = {
    ("1st", "singular"): "yo",
    ("2nd", "singular"): "tú",
    ("3rd", "singular"): "él/ella",
    ("1st", "plural"): "nosotros/nosotras",
    ("2nd", "plural"): "vosotros/vosotras",
    ("3rd", "plural"): "ellos/ellas",
}

PERSON_NUMBER_TO_SLOT: dict[tuple[str, str], int] = {
    ("1st", "singular"): 0,
    ("2nd", "singular"): 1,
    ("3rd", "singular"): 2,
    ("1st", "plural"): 3,
    ("2nd", "plural"): 4,
    ("3rd", "plural"): 5,
}

PERSON_LABELS = ("yo", "tú", "él", "nosotros", "vosotros", "ellos")


@dataclass
class GridCell:
    id: str
    keyword: str
    translation: str
    tense: str
    person: str
    number: str
    expected_form: str
    cefr_level: str | None
    prompt: str
    paradigm_gold: str


def build_full_paradigm_prompt(*, lemma: str, tense: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    return (
        f'Conjugate the Spanish verb "{lemma}" in the {tense_label} tense.\n'
        "List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.\n"
        "Reply with only the six conjugated verb forms in that tense, one per line."
    )


def build_single_slot_prompt(*, lemma: str, tense: str, person: str, number: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    subject_hint = SUBJECT_HINTS[(person, number)]
    return (
        f'Conjugate the Spanish verb "{lemma}" in the {tense_label} tense.\n'
        f"Give the form for ({person} person, {number}) — this is the {subject_hint} form.\n"
        "Reply with only that one conjugated verb in that specific tense and form — "
        "one word, no sentence, no infinitive, no explanation."
    )


def paradigm_gold_form(*, lemma: str, tense: str, person: str, number: str) -> str:
    slot = PERSON_NUMBER_TO_SLOT[(person, number)]
    return PARADIGMS[lemma]["tenses"][tense][slot]


def load_grid_cells(benchmark_name: str) -> list[GridCell]:
    path = _BENCHMARKS_DIR / f"{benchmark_name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cells: list[GridCell] = []
    for i, cs in enumerate(data["constraint_sets"]):
        extract_constraints(cs)
        lemma = cs["keyword"]
        tense = cs["tense"]
        person = cs["person"]
        number = cs["number"]
        expected = cs["expected_form"]
        if lemma not in PARADIGMS:
            raise KeyError(f"No PARADIGMS entry for {lemma!r}")
        gold = paradigm_gold_form(lemma=lemma, tense=tense, person=person, number=number)
        if _normalize(gold) != _normalize(expected):
            raise ValueError(
                f"Gold mismatch {lemma} {tense} {person} {number}: "
                f"YAML={expected!r} PARADIGMS={gold!r}"
            )
        cell_id = f"{benchmark_name}__{lemma}__{tense}_{person}_{number}__{i}"
        cells.append(
            GridCell(
                id=cell_id,
                keyword=lemma,
                translation=cs["translation"],
                tense=tense,
                person=person,
                number=number,
                expected_form=expected,
                cefr_level=cs.get("cefr_level"),
                prompt=build_single_slot_prompt(
                    lemma=lemma, tense=tense, person=person, number=number
                ),
                paradigm_gold=gold,
            )
        )
    return cells


def score_knowledge(raw: str, expected_form: str) -> dict[str, Any]:
    stripped = raw.strip()
    norm_expected = _normalize(expected_form)
    norm_stripped = _normalize(stripped)
    tokens = _tokenize_spanish(raw)
    norm_tokens = [_normalize(t) for t in tokens]

    exact = norm_stripped == norm_expected
    token_exact = norm_expected in norm_tokens
    only_token = len(norm_tokens) == 1 and token_exact

    return {
        "raw": stripped,
        "exact_match": exact,
        "token_match": token_exact,
        "only_token_match": only_token,
        "knowledge_hit": only_token or exact or token_exact,
        "parsed_tokens": tokens,
    }


def cell_key(keyword: str, tense: str, person: str, number: str) -> tuple[str, str, str, str]:
    return (keyword, tense, person, number)


def load_sentence_ef_by_cell(
    *,
    experiment_id: int,
    benchmark_name: str,
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    session = SessionLocal()
    try:
        exp = session.get(Experiment, experiment_id)
        if exp is None:
            raise ValueError(f"Experiment id={experiment_id} not found")
        benchmark = session.query(Benchmark).filter_by(name=benchmark_name).one()
        out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for cs in benchmark.constraint_sets:
            key = cell_key(cs.keyword, cs.tense, cs.person, cs.number)
            sentences = (
                session.query(GeneratedSentence)
                .options(joinedload(GeneratedSentence.evaluations))
                .filter_by(experiment_id=experiment_id, constraint_set_id=cs.id)
                .all()
            )
            ef_pass = sum(
                1
                for s in sentences
                for ev in s.evaluations
                if ev.evaluator_name == "expected_form_match" and ev.score >= 1.0
            )
            out[key] = {
                "experiment_id": experiment_id,
                "experiment_name": exp.name,
                "constraint_set_id": cs.id,
                "n": len(sentences),
                "ef_pass": ef_pass,
                "ef_rate": round(ef_pass / len(sentences), 4) if sentences else None,
            }
        return out
    finally:
        session.close()


def run_single_slot_probe(
    model_key: str,
    cells: list[GridCell],
    *,
    temperature: float,
) -> list[dict[str, Any]]:
    model_id = QWEN_MODELS[model_key]
    rows: list[dict[str, Any]] = []
    for i, cell in enumerate(cells, 1):
        print(f"  [{i}/{len(cells)}] {cell.keyword} {cell.tense} {cell.person} {cell.number}...", flush=True)
        t0 = time.perf_counter()
        raw = complete_single_slot(model_id, cell.prompt, temperature=temperature)
        scored = score_knowledge(raw, cell.expected_form)
        rows.append(
            {
                "cell": asdict(cell),
                "latency_s": round(time.perf_counter() - t0, 3),
                **scored,
            }
        )
    return rows


def run_full_paradigm_probe(
    model_key: str,
    cells: list[GridCell],
    *,
    temperature: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (per-cell rows, per verb×tense paradigm call records)."""
    model_id = QWEN_MODELS[model_key]
    pairs: dict[tuple[str, str], str] = {}
    for cell in cells:
        pairs.setdefault((cell.keyword, cell.tense), build_full_paradigm_prompt(
            lemma=cell.keyword, tense=cell.tense
        ))

    paradigm_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for i, ((lemma, tense), prompt) in enumerate(sorted(pairs.items()), 1):
        print(f"  [{i}/{len(pairs)}] {lemma} {tense} (six forms)...", flush=True)
        t0 = time.perf_counter()
        raw = complete_paradigm(model_id, prompt, temperature=temperature)
        case = ParadigmCase(
            id=f"{lemma}__{tense}",
            lemma=lemma,
            tier=PARADIGMS[lemma]["tier"],
            tense=tense,
            expected=PARADIGMS[lemma]["tenses"][tense],
            prompt=prompt,
        )
        scored = score_paradigm(case, raw)
        paradigm_by_key[(lemma, tense)] = {
            "lemma": lemma,
            "tense": tense,
            "prompt": prompt,
            "latency_s": round(time.perf_counter() - t0, 3),
            **scored,
        }

    rows: list[dict[str, Any]] = []
    for cell in cells:
        pk = (cell.keyword, cell.tense)
        paradigm = paradigm_by_key[pk]
        slot = PERSON_NUMBER_TO_SLOT[(cell.person, cell.number)]
        slot_info = paradigm["per_person"][slot]
        rows.append(
            {
                "cell": asdict(cell),
                "paradigm_call_id": f"{cell.keyword}__{cell.tense}",
                "latency_s": paradigm["latency_s"],
                "raw": paradigm["raw"],
                "target_slot": PERSON_LABELS[slot],
                "target_expected": slot_info["expected"],
                "knowledge_hit": slot_info["found"],
                "paradigm_forms_found": paradigm["forms_found"],
                "paradigm_forms_total": paradigm["forms_total"],
            }
        )
    return rows, [paradigm_by_key[k] for k in sorted(paradigm_by_key)]


def run_knowledge_probe(
    model_key: str,
    cells: list[GridCell],
    *,
    probe_mode: str,
    temperature: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
    if probe_mode == "single_slot":
        return run_single_slot_probe(model_key, cells, temperature=temperature), None
    if probe_mode == "full_paradigm":
        return run_full_paradigm_probe(model_key, cells, temperature=temperature)
    raise ValueError(f"Unknown probe_mode: {probe_mode!r}")


def summarize_joined(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    k_knowledge = sum(1 for r in rows if r["knowledge_hit"])
    dissociation = [
        r
        for r in rows
        if r["knowledge_hit"] and (r.get("sentence_baseline") or {}).get("ef_pass", 0) <= 2
    ]
    both_pass = [
        r
        for r in rows
        if r["knowledge_hit"]
        and (r.get("sentence_baseline") or {}).get("ef_pass", 0) >= 8
    ]
    knowledge_fail = [r for r in rows if not r["knowledge_hit"]]

    def mean_ef(field: str) -> float | None:
        rates = [
            r[field]["ef_rate"]
            for r in rows
            if r.get(field) and r[field].get("ef_rate") is not None
        ]
        return round(sum(rates) / len(rates), 4) if rates else None

    lo, hi = wilson_ci(k_knowledge, n)
    return {
        "cells_total": n,
        "knowledge_hits": k_knowledge,
        "knowledge_rate": round(k_knowledge / n, 4) if n else None,
        "knowledge_wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
        "mean_sentence_baseline_ef": mean_ef("sentence_baseline"),
        "mean_sentence_form_injected_ef": mean_ef("sentence_form_injected"),
        "dissociation_count": len(dissociation),
        "dissociation_rate": round(len(dissociation) / n, 4) if n else None,
        "both_pass_count": len(both_pass),
        "knowledge_fail_count": len(knowledge_fail),
    }


def print_analysis(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    print("\n=== HEADLINE ===")
    print(
        f"Knowledge: {summary['knowledge_hits']}/{summary['cells_total']} "
        f"({summary['knowledge_rate']:.1%})"
    )
    print(f"Mean sentence baseline EF: {summary['mean_sentence_baseline_ef']:.1%}")
    if summary.get("mean_sentence_form_injected_ef") is not None:
        print(
            f"Mean sentence form-injected EF: "
            f"{summary['mean_sentence_form_injected_ef']:.1%}"
        )
    print(
        f"Dissociation (knowledge ✓, baseline EF ≤2/10): "
        f"{summary['dissociation_count']}/{summary['cells_total']}"
    )

    print("\n=== BY TENSE (baseline EF) ===")
    by_tense: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_tense.setdefault(r["cell"]["tense"], []).append(r)
    for tense, group in sorted(by_tense.items()):
        k = sum(1 for r in group if r["knowledge_hit"])
        ef = sum(r["sentence_baseline"]["ef_pass"] for r in group)
        n = sum(r["sentence_baseline"]["n"] for r in group)
        print(f"  {tense:12s}  knowledge {k}/{len(group)}  baseline EF {ef}/{n}")

    print("\n=== DISSOCIATION CELLS ===")
    for r in rows:
        sb = r["sentence_baseline"]
        if r["knowledge_hit"] and sb["ef_pass"] <= 2:
            print(
                f"  {r['cell']['keyword']:8s} {r['cell']['tense']:12s} "
                f"{r['cell']['person']} {r['cell']['number']:8s} "
                f"gold={r['cell']['expected_form']!r}  "
                f"knowledge={r['raw']!r}  baseline EF {sb['ef_pass']}/{sb['n']}"
            )

    print("\n=== KNOWLEDGE FAILURES ===")
    for r in rows:
        if not r["knowledge_hit"]:
            print(
                f"  {r['cell']['keyword']:8s} {r['cell']['tense']:12s} "
                f"gold={r['cell']['expected_form']!r}  got={r['raw']!r}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Knowledge probe joined with spanish_basic_grid sentence EF"
    )
    parser.add_argument(
        "--probe-mode",
        choices=("single_slot", "full_paradigm"),
        default="single_slot",
    )
    parser.add_argument("--benchmark", default="spanish_basic_grid")
    parser.add_argument("--models", nargs="+", choices=list(QWEN_MODELS), default=["qwen17b"])
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--sentence-experiment-id", type=int, default=15)
    parser.add_argument("--form-injected-experiment-id", type=int, default=16)
    parser.add_argument("--skip-knowledge", action="store_true", help="Only join DB (debug)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    cells = load_grid_cells(args.benchmark)
    print(f"Loaded {len(cells)} cells from {args.benchmark}")

    baseline_ef = load_sentence_ef_by_cell(
        experiment_id=args.sentence_experiment_id,
        benchmark_name=args.benchmark,
    )
    form_injected_ef = load_sentence_ef_by_cell(
        experiment_id=args.form_injected_experiment_id,
        benchmark_name=args.benchmark,
    )

    if args.dry_run:
        print(f"\nProbe mode: {args.probe_mode}")
        if args.probe_mode == "full_paradigm":
            print("\nSample prompt (escribir preterite):")
            print(build_full_paradigm_prompt(lemma="escribir", tense="preterite"))
        else:
            print("\nSample prompt (escribir future 2pl):")
            sample = next(
                c
                for c in cells
                if c.keyword == "escribir" and c.tense == "future" and c.person == "2nd"
            )
            print(sample.prompt)
        return

    results: dict[str, Any] = {
        "probe_mode": args.probe_mode,
        "prompt_version": PROMPT_VERSIONS[args.probe_mode],
        "benchmark": args.benchmark,
        "temperature": args.temperature,
        "sentence_baseline_experiment_id": args.sentence_experiment_id,
        "sentence_form_injected_experiment_id": args.form_injected_experiment_id,
        "by_model": {},
    }

    for model_key in args.models:
        print(f"\n=== {model_key} ({QWEN_MODELS[model_key]}) ===")
        t0 = time.perf_counter()
        paradigm_calls = None
        if args.skip_knowledge:
            knowledge_rows = [
                {
                    "cell": asdict(c),
                    "knowledge_hit": None,
                    "raw": None,
                }
                for c in cells
            ]
        else:
            knowledge_rows, paradigm_calls = run_knowledge_probe(
                model_key,
                cells,
                probe_mode=args.probe_mode,
                temperature=args.temperature,
            )

        joined: list[dict[str, Any]] = []
        for row in knowledge_rows:
            c = row["cell"]
            key = cell_key(c["keyword"], c["tense"], c["person"], c["number"])
            sb = baseline_ef.get(key)
            si = form_injected_ef.get(key)
            if sb is None:
                raise KeyError(f"No baseline EF for cell {key}")
            dissociation = bool(
                row.get("knowledge_hit")
                and sb["ef_pass"] <= 2
            )
            joined.append(
                {
                    **row,
                    "sentence_baseline": sb,
                    "sentence_form_injected": si,
                    "dissociation": dissociation,
                }
            )

        summary = summarize_joined(joined)
        block: dict[str, Any] = {
            "model_id": QWEN_MODELS[model_key],
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "summary": summary,
            "cells": joined,
        }
        if paradigm_calls is not None:
            block["paradigm_calls"] = paradigm_calls
        results["by_model"][model_key] = block
        print_analysis(joined, summary)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
