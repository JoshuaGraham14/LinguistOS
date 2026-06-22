#!/usr/bin/env python3
"""Spanish verb spike — Qwen ladder (prototyping; not the pipeline).

Mirror of ``english_rare_verbs_qwen_spike.py``: tests whether small Qwen models
can *recognise* and *conjugate* Spanish verbs in isolation.

Tiers (gold forms from existing benchmarks / RAE-style paradigms):
  - common_regular   — spanish_basic (high-frequency, regular morphology)
  - common_irregular — spanish_challenging (frequent but irregular)
  - rare             — spanish_niche (low-frequency literary / formal verbs)

Pair with the English spike to separate multilingual-data gaps from capacity gaps
at the same model size.

Results: docs/spike-results/eval_spanish_verbs_qwen_spike_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Status:      Diagnostic spike (Experiment 2). Not run through
             ``research.run_experiment`` or the DB pipeline. This is a
             one-word isolation probe (no sentence generation), so the
             sentence-level evaluator stack does not apply; this script
             is the reproducible artifact.

Run:         python3 -m research.prototyping.spanish_verbs_qwen_spike
             (run from repo root; no CLI flags required)

Output:      docs/spike-results/eval_spanish_verbs_qwen_spike_results.json
             Writeup: docs/experiment-results/english_spanish_verb_isolation_qwen_spike.md

Stimuli:     20 Spanish verbs across three tiers (5 common regular,
             8 common irregular, 7 rare), drawn from the spanish_basic,
             spanish_challenging, and spanish_niche benchmark YAMLs.

Models:      Qwen/Qwen2.5-0.5B-Instruct, Qwen/Qwen3-1.7B,
             Qwen/Qwen3-4B-Instruct-2507 (HuggingFace, MPS or CPU).

Decoding:    Greedy (temperature=0, do_sample=False), max_new_tokens=32,
             one sample per probe. Qwen3 thinking mode disabled.
             Greedy is deterministic; no seed required.

Scoring:     Unicode NFC + casefold exact-match against the gold form.

Original run: 2026-06-12 (results committed in batch ~16:43 GMT+1).
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import math
import re
import string
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"

QWEN_MODELS: dict[str, str] = {
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B-Instruct-2507",
}


@dataclass(frozen=True)
class VerbEntry:
    lemma: str
    gloss: str
    tier: str  # common_regular | common_irregular | rare
    forms: dict[str, list[str]] = field(default_factory=dict)
    notes: str = ""


# One conjugation probe per verb; forms match research/benchmarks/*.yaml.
VERB_ENTRIES: list[VerbEntry] = [
    # ── common_regular (spanish_basic) ───────────────────────────────────────
    VerbEntry(
        lemma="comer",
        gloss="to eat",
        tier="common_regular",
        forms={"first person plural preterite (nosotros)": ["comimos"]},
    ),
    VerbEntry(
        lemma="vivir",
        gloss="to live",
        tier="common_regular",
        forms={"third person singular future": ["vivirá"]},
    ),
    VerbEntry(
        lemma="hablar",
        gloss="to speak",
        tier="common_regular",
        forms={"second person singular present (tú)": ["hablas"]},
    ),
    VerbEntry(
        lemma="escribir",
        gloss="to write",
        tier="common_regular",
        forms={"third person plural preterite (ellos)": ["escribieron"]},
    ),
    VerbEntry(
        lemma="correr",
        gloss="to run",
        tier="common_regular",
        forms={"first person singular present (yo)": ["corro"]},
    ),
    # ── common_irregular (spanish_challenging) ───────────────────────────────
    VerbEntry(
        lemma="pedir",
        gloss="to ask for",
        tier="common_irregular",
        forms={"first person singular present (yo)": ["pido"]},
    ),
    VerbEntry(
        lemma="dormir",
        gloss="to sleep",
        tier="common_irregular",
        forms={"first person singular present (yo)": ["duermo"]},
    ),
    VerbEntry(
        lemma="decir",
        gloss="to say",
        tier="common_irregular",
        forms={"first person singular preterite (yo)": ["dije"]},
    ),
    VerbEntry(
        lemma="tener",
        gloss="to have",
        tier="common_irregular",
        forms={"third person plural preterite (ellos)": ["tuvieron"]},
    ),
    VerbEntry(
        lemma="conducir",
        gloss="to drive",
        tier="common_irregular",
        forms={"third person plural preterite (ellos)": ["condujeron"]},
    ),
    VerbEntry(
        lemma="poner",
        gloss="to put",
        tier="common_irregular",
        forms={"first person singular conditional (yo)": ["pondría"]},
    ),
    VerbEntry(
        lemma="venir",
        gloss="to come",
        tier="common_irregular",
        forms={"first person singular conditional (yo)": ["vendría"]},
    ),
    VerbEntry(
        lemma="llegar",
        gloss="to arrive",
        tier="common_irregular",
        forms={"first person singular preterite (yo)": ["llegué"]},
    ),
    # ── rare (spanish_niche) ─────────────────────────────────────────────────
    VerbEntry(
        lemma="henchir",
        gloss="to fill (literary)",
        tier="rare",
        forms={"first person singular preterite (yo)": ["henchí"]},
    ),
    VerbEntry(
        lemma="argüir",
        gloss="to argue (formally)",
        tier="rare",
        forms={"first person singular preterite (yo)": ["argüí"]},
    ),
    VerbEntry(
        lemma="atestiguar",
        gloss="to testify",
        tier="rare",
        forms={"first person singular preterite (yo)": ["atestigüé"]},
    ),
    VerbEntry(
        lemma="menguar",
        gloss="to diminish",
        tier="rare",
        forms={"first person singular present (yo)": ["menguo"]},
    ),
    VerbEntry(
        lemma="empalagar",
        gloss="to cloy",
        tier="rare",
        forms={"first person singular present (yo)": ["empalago"]},
    ),
    VerbEntry(
        lemma="blandir",
        gloss="to brandish",
        tier="rare",
        forms={"first person singular preterite (yo)": ["blandí"]},
    ),
    VerbEntry(
        lemma="proferir",
        gloss="to utter (threats or insults)",
        tier="rare",
        forms={"first person singular present (yo)": ["profiero"]},
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
    text = unicodedata.normalize("NFC", text)
    return text.strip(_EDGE_PUNCT).casefold()


def _first_token(text: str) -> str:
    cleaned = _strip_thinking(text).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response|respuesta)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    match = re.search(r"[\w\u00C0-\u024F]+", cleaned, flags=re.UNICODE)
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


def build_cases(tasks: set[str]) -> list[ProbeCase]:
    cases: list[ProbeCase] = []
    for entry in VERB_ENTRIES:
        if "recognition" in tasks:
            prompt = (
                "What is the base form (infinitive) of the Spanish verb that means "
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
                    f"What is the {form_label} of the Spanish verb "
                    f'"{entry.lemma}" (meaning: {entry.gloss})? Reply with one word only.'
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
        "You are a precise Spanish morphology assistant. "
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


def _rate(
    rows: list[dict[str, Any]],
    *,
    task: str | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
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
            "conjugation_common_regular": _rate(
                rows, task="conjugation", tier="common_regular"
            ),
            "conjugation_common_irregular": _rate(
                rows, task="conjugation", tier="common_irregular"
            ),
            "conjugation_rare": _rate(rows, task="conjugation", tier="rare"),
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
        description="Spanish verb recognition + conjugation spike (Qwen ladder)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(QWEN_MODELS),
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=["recognition", "conjugation"],
        default=["recognition", "conjugation"],
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    tasks = set(args.tasks)

    if args.dry_run:
        cases = build_cases(tasks)
        print(json.dumps([asdict(c) for c in cases], indent=2, ensure_ascii=False))
        print(f"\n{len(cases)} cases × {len(args.models)} models")
        return

    print(
        f"Spanish verb spike: {len(VERB_ENTRIES)} verbs, "
        f"{len(build_cases(tasks))} probes, models={args.models}, temp={args.temperature}"
    )
    data = run_spike(args.models, tasks=tasks, temperature=args.temperature)

    out_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "spike-results"
        / "eval_spanish_verbs_qwen_spike_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
