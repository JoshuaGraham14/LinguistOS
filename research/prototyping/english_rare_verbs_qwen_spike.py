#!/usr/bin/env python3
"""English rare-verb spike — Qwen ladder (prototyping; not the pipeline).

Diagnostic for Tom meeting #7 (A6): can small multilingual Qwen models
*recognise* rare English verbs and *produce* non-trivial inflected forms?

Two lightweight tasks (no benchmark DB, no evaluator pipeline):
  1. recognition — given a gloss, return the base-form lemma
  2. conjugation — given lemma + form label, return one surface form

Models (same ladder as baseline_hf presets):
  - Qwen/Qwen2.5-0.5B-Instruct
  - Qwen/Qwen3-1.7B
  - Qwen/Qwen3-4B-Instruct-2507

Gold forms are standard dictionary entries (OED / Merriam-Webster style);
alternate spellings are accepted where both are listed.

Results: docs/eval_english_rare_verbs_qwen_spike_results.json
"""

from __future__ import annotations

import json
import math
import re
import string
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking

_EDGE_PUNCT = string.punctuation + "«»""''"

QWEN_MODELS: dict[str, str] = {
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B-Instruct-2507",
}


@dataclass(frozen=True)
class VerbEntry:
    lemma: str
    gloss: str
    tier: str  # common_irregular | rare_irregular
    forms: dict[str, list[str]] = field(default_factory=dict)
    notes: str = ""


# Gold forms: primary + accepted alternates (both listed in major dictionaries).
VERB_ENTRIES: list[VerbEntry] = [
    # ── Tier 1: irregular but high-frequency ─────────────────────────────────
    VerbEntry(
        lemma="rise",
        gloss="to move upward or increase",
        tier="common_irregular",
        forms={"past tense": ["rose"], "past participle": ["risen"]},
    ),
    VerbEntry(
        lemma="lay",
        gloss="to put or place something down",
        tier="common_irregular",
        forms={"past tense": ["laid"], "past participle": ["laid"]},
        notes="Distinct from lie (recline).",
    ),
    VerbEntry(
        lemma="swim",
        gloss="to move through water",
        tier="common_irregular",
        forms={"past tense": ["swam"], "past participle": ["swum"]},
    ),
    VerbEntry(
        lemma="steal",
        gloss="to take without permission",
        tier="common_irregular",
        forms={"past tense": ["stole"], "past participle": ["stolen"]},
    ),
    VerbEntry(
        lemma="bind",
        gloss="to tie or fasten",
        tier="common_irregular",
        forms={"past tense": ["bound"], "past participle": ["bound"]},
    ),
    VerbEntry(
        lemma="forgo",
        gloss="to go without; abstain from",
        tier="common_irregular",
        forms={"past tense": ["forwent"], "past participle": ["forgone"]},
        notes="Also spelled forego (same forms).",
    ),
    # ── Tier 2: rare / literary / archaic irregular ──────────────────────────
    VerbEntry(
        lemma="gainsay",
        gloss="to deny or contradict",
        tier="rare_irregular",
        forms={"past tense": ["gainsaid"], "past participle": ["gainsaid"]},
    ),
    VerbEntry(
        lemma="beseech",
        gloss="to implore or beg earnestly",
        tier="rare_irregular",
        forms={
            "past tense": ["besought", "beseeched"],
            "past participle": ["besought", "beseeched"],
        },
    ),
    VerbEntry(
        lemma="smite",
        gloss="to strike heavily",
        tier="rare_irregular",
        forms={"past tense": ["smote"], "past participle": ["smitten", "smote"]},
    ),
    VerbEntry(
        lemma="shrive",
        gloss="to hear confession and grant absolution",
        tier="rare_irregular",
        forms={
            "past tense": ["shrove", "shrived"],
            "past participle": ["shriven", "shrived"],
        },
    ),
    VerbEntry(
        lemma="cleave",
        gloss="to split or sever",
        tier="rare_irregular",
        forms={
            "past tense": ["cleft", "clove", "cleaved"],
            "past participle": ["cleft", "cloven", "cleaved"],
        },
        notes="Split sense only (not cleave=adhere).",
    ),
    VerbEntry(
        lemma="gird",
        gloss="to encircle or prepare oneself",
        tier="rare_irregular",
        forms={
            "past tense": ["girt", "girded"],
            "past participle": ["girt", "girded"],
        },
    ),
    VerbEntry(
        lemma="forswear",
        gloss="to renounce or perjure oneself",
        tier="rare_irregular",
        forms={"past tense": ["forswore"], "past participle": ["forsworn"]},
    ),
    VerbEntry(
        lemma="betide",
        gloss="to happen to; befall",
        tier="rare_irregular",
        forms={
            "past tense": ["betid", "betided"],
            "past participle": ["betid", "betided"],
        },
    ),
    VerbEntry(
        lemma="clothe",
        gloss="to dress or provide with clothing",
        tier="rare_irregular",
        forms={
            "past tense": ["clad", "clothed"],
            "past participle": ["clad", "clothed"],
        },
    ),
    VerbEntry(
        lemma="wreak",
        gloss="to inflict or cause (e.g. havoc)",
        tier="rare_irregular",
        forms={"past tense": ["wreaked", "wrought"], "past participle": ["wreaked"]},
        notes="wrought is archaic/literary for past of wreak in some uses.",
    ),
]


@dataclass
class ProbeCase:
    id: str
    task: str  # recognition | conjugation
    lemma: str
    gloss: str
    tier: str
    form_label: str | None
    expected: list[str]
    prompt: str


def _normalize(text: str) -> str:
    return text.strip(_EDGE_PUNCT).casefold()


def _first_token(text: str) -> str:
    cleaned = _strip_thinking(text).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    match = re.search(r"[A-Za-z][A-Za-z'-]*", cleaned)
    return match.group(0) if match else cleaned


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def build_cases(tasks: set[str]) -> list[ProbeCase]:
    cases: list[ProbeCase] = []
    for entry in VERB_ENTRIES:
        if "recognition" in tasks:
            prompt = (
                f"What is the base form (infinitive) of the English verb that means "
                f'"{entry.gloss}"? Reply with one word only.'
            )
            cases.append(
                ProbeCase(
                    id=f"{entry.lemma}__recognition",
                    task="recognition",
                    lemma=entry.lemma,
                    gloss=entry.gloss,
                    tier=entry.tier,
                    form_label=None,
                    expected=[entry.lemma],
                    prompt=prompt,
                )
            )
        if "conjugation" in tasks:
            for form_label, gold in entry.forms.items():
                prompt = (
                    f'What is the {form_label} of the English verb "{entry.lemma}" '
                    f'(meaning: {entry.gloss})? Reply with one word only.'
                )
                cases.append(
                    ProbeCase(
                        id=f"{entry.lemma}__{form_label.replace(' ', '_')}",
                        task="conjugation",
                        lemma=entry.lemma,
                        gloss=entry.gloss,
                        tier=entry.tier,
                        form_label=form_label,
                        expected=gold,
                        prompt=prompt,
                    )
                )
    return cases


def complete(model_id: str, prompt: str, *, temperature: float) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    system = (
        "You are a precise English morphology assistant. "
        "Follow the instruction exactly. Give only the requested word."
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
        "max_new_tokens": 32,
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


def score_response(case: ProbeCase, raw: str) -> dict[str, Any]:
    token = _first_token(raw)
    norm = _normalize(token)
    expected_norm = {_normalize(e) for e in case.expected}
    lemma_norm = _normalize(case.lemma)
    return {
        "raw": raw.strip(),
        "parsed_token": token,
        "correct": norm in expected_norm,
        "infinitive_fallback": case.task == "conjugation" and norm == lemma_norm,
        "expected": case.expected,
    }


def run_spike(
    model_keys: list[str],
    *,
    tasks: set[str],
    temperature: float,
) -> dict[str, Any]:
    cases = build_cases(tasks)
    results: dict[str, Any] = {
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "temperature": temperature,
        "tasks": sorted(tasks),
        "verb_entries": [asdict(v) for v in VERB_ENTRIES],
        "by_model": {},
    }

    for key in model_keys:
        model_id = QWEN_MODELS[key]
        print(f"\n=== {key} ({model_id}) ===")
        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case.id}...", flush=True)
            t_case = time.perf_counter()
            raw = complete(model_id, case.prompt, temperature=temperature)
            scored = score_response(case, raw)
            rows.append(
                {
                    "case": asdict(case),
                    "latency_s": round(time.perf_counter() - t_case, 3),
                    **scored,
                }
            )
        results["by_model"][key] = {
            "model_id": model_id,
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "results": rows,
        }
    results["summary"] = summarize(results)
    return results


def _infinitive_fallback(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conj = [r for r in rows if r["case"]["task"] == "conjugation"]
    n = len(conj)
    k = sum(1 for r in conj if r.get("infinitive_fallback"))
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "fallback_count": k,
        "fallback_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def _rate(rows: list[dict[str, Any]], *, task: str | None = None, tier: str | None = None) -> dict[str, Any]:
    filtered = rows
    if task:
        filtered = [r for r in filtered if r["case"]["task"] == task]
    if tier:
        filtered = [r for r in filtered if r["case"]["tier"] == tier]
    n = len(filtered)
    k = sum(1 for r in filtered if r["correct"])
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}}
    for key, block in data["by_model"].items():
        rows = block["results"]
        out["per_model"][key] = {
            "overall": _rate(rows),
            "recognition": _rate(rows, task="recognition"),
            "conjugation": _rate(rows, task="conjugation"),
            "conjugation_common_irregular": _rate(
                rows, task="conjugation", tier="common_irregular"
            ),
            "conjugation_rare_irregular": _rate(
                rows, task="conjugation", tier="rare_irregular"
            ),
            "infinitive_fallback": _infinitive_fallback(rows),
            "failures": [
                {
                    "id": r["case"]["id"],
                    "expected": r["expected"],
                    "got": r["parsed_token"],
                    "raw": r["raw"],
                }
                for r in rows
                if not r["correct"]
            ],
        }
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="English rare-verb recognition + conjugation spike (Qwen ladder)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(QWEN_MODELS),
        help="Which Qwen checkpoints to run (default: all three)",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=["recognition", "conjugation"],
        default=["recognition", "conjugation"],
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="0 = greedy decode (recommended for this diagnostic)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cases and exit without loading models",
    )
    args = parser.parse_args()
    tasks = set(args.tasks)

    if args.dry_run:
        cases = build_cases(tasks)
        print(json.dumps([asdict(c) for c in cases], indent=2, ensure_ascii=False))
        print(f"\n{len(cases)} cases × {len(args.models)} models")
        return

    print(
        f"English rare-verb spike: {len(VERB_ENTRIES)} verbs, "
        f"{len(build_cases(tasks))} probes, models={args.models}, temp={args.temperature}"
    )
    data = run_spike(args.models, tasks=tasks, temperature=args.temperature)

    out_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "eval_english_rare_verbs_qwen_spike_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
