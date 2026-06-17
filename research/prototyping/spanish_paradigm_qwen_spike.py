#!/usr/bin/env python3
"""Spanish full-paradigm spike — Qwen ladder (prototyping; not the pipeline).

One verb × one tense per call. Checks whether models can *produce* full
conjugation paradigms (knowledge / capacity) vs failing only when forms
must appear inside generated sentences (CTG / binding).

Five verbs × five indicative tenses × six persons = 30 gold forms per verb.
Scoring: each expected surface form matched anywhere in the model output
(order-independent; accent-normalised).

Results: docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Status:      Diagnostic spike (Experiment 3). Intentionally standalone:
             this probes paradigm knowledge (free-form list of six forms
             per tense), not sentence generation under ortho-syntactic
             constraints — so it does not fit the sentence-level
             ``expected_form_match`` / LanguageTool / length-band stack
             that the rest of the framework is built around. The script
             itself is the reproducible artifact.

Run:         python3 -m research.prototyping.spanish_paradigm_qwen_spike
             (run from repo root; no CLI flags required)

Output:      docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json
             Headline writeup (explicit_v1):
               docs/experiment-results/spanish_paradigm_qwen_explicit_prompt_evaluation.md

Stimuli:     5 verbs × 5 indicative tenses × 6 persons = 150 gold slots
             per model. Verb mix: 2 common regular (comer, hablar),
             1 common irregular (tener), 2 rare (blandir, argüir).

Models:      Qwen/Qwen2.5-0.5B-Instruct, Qwen/Qwen3-1.7B,
             Qwen/Qwen3-4B-Instruct-2507 (HuggingFace, MPS or CPU).
             4B was NOT re-run under explicit_v1: at the time of the
             explicit re-run, 4B common-paradigm recall was already
             at ceiling under the minimal prompt and a re-run would not
             have moved the headline. This means the 0.5B / 1.7B and
             4B numbers in the writeup come from DIFFERENT prompt
             versions, by design. Do not cite the three together as
             a single ladder without flagging this.

Decoding:    Greedy (temperature=0, do_sample=False), max_new_tokens=256,
             one sample per call. Qwen3 thinking mode disabled.
             Deterministic; no seed required.

Scoring:     Each gold surface form matched anywhere in the output
             (Unicode NFC + casefold). This is INTENTIONALLY lenient,
             order-independent substring matching: the purpose is to
             ask 'can the model produce these forms at all when not
             constrained?', not to test exact slot binding. A known
             consequence is that surface-form collisions across
             persons (e.g. ``comía`` is both yo and él/ella imperfect)
             can be credited to both slots from a single mention. The
             slot-by-slot exact-binding probe lives in
             ``cross_language_morphology_qwen_spike.py`` (Exp 1B/2B).

Prompt:     ``explicit_v1`` (PROMPT_VERSION constant at top of file).
             A prior ``minimal`` prompt ("{lemma}, {tense} tense.") was
             tested first and performed much worse, especially on 1.7B
             (25% recall vs 73% under explicit_v1). The switch was
             deliberate — the original prompt was failing to convey
             the task at small model scales, which is itself a
             diagnostic finding documented in the writeup. To
             reproduce the minimal-prompt baseline, see the archived
             results at
             ``docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json``
             (look for ``prompt_version`` field).

Original run: 2026-06-12 (explicit_v1 results committed in batch
              ~16:43 GMT+1).
----------------------------------------------------------------------
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking

QWEN_MODELS: dict[str, str] = {
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B-Instruct-2507",
}

# yo, tú, él/ella, nosotros, vosotros, ellos/ellas
PERSON_LABELS = ("yo", "tú", "él", "nosotros", "vosotros", "ellos")

TENSES: tuple[str, ...] = ("present", "preterite", "imperfect", "future", "conditional")

# Gold paradigms (indicative); sources: RAE / SpanishDict-style paradigms.
PARADIGMS: dict[str, dict[str, Any]] = {
    "comer": {
        "tier": "common_regular",
        "tenses": {
            "present": ["como", "comes", "come", "comemos", "coméis", "comen"],
            "preterite": ["comí", "comiste", "comió", "comimos", "comisteis", "comieron"],
            "imperfect": ["comía", "comías", "comía", "comíamos", "comíais", "comían"],
            "future": ["comeré", "comerás", "comerá", "comeremos", "comeréis", "comerán"],
            "conditional": [
                "comería",
                "comerías",
                "comería",
                "comeríamos",
                "comeríais",
                "comerían",
            ],
        },
    },
    "hablar": {
        "tier": "common_regular",
        "tenses": {
            "present": ["hablo", "hablas", "habla", "hablamos", "habláis", "hablan"],
            "preterite": ["hablé", "hablaste", "habló", "hablamos", "hablasteis", "hablaron"],
            "imperfect": ["hablaba", "hablabas", "hablaba", "hablábamos", "hablabais", "hablaban"],
            "future": ["hablaré", "hablarás", "hablará", "hablaremos", "hablaréis", "hablarán"],
            "conditional": [
                "hablaría",
                "hablarías",
                "hablaría",
                "hablaríamos",
                "hablaríais",
                "hablarían",
            ],
        },
    },
    "tener": {
        "tier": "common_irregular",
        "tenses": {
            "present": ["tengo", "tienes", "tiene", "tenemos", "tenéis", "tienen"],
            "preterite": ["tuve", "tuviste", "tuvo", "tuvimos", "tuvisteis", "tuvieron"],
            "imperfect": ["tenía", "tenías", "tenía", "teníamos", "teníais", "tenían"],
            "future": ["tendré", "tendrás", "tendrá", "tendremos", "tendréis", "tendrán"],
            "conditional": [
                "tendría",
                "tendrías",
                "tendría",
                "tendríamos",
                "tendríais",
                "tendrían",
            ],
        },
    },
    "blandir": {
        "tier": "rare",
        "tenses": {
            "present": ["blando", "blandes", "blande", "blandimos", "blandís", "blanden"],
            "preterite": ["blandí", "blandiste", "blandió", "blandimos", "blandisteis", "blandieron"],
            "imperfect": ["blandía", "blandías", "blandía", "blandíamos", "blandíais", "blandían"],
            "future": ["blandiré", "blandirás", "blandirá", "blandiremos", "blandiréis", "blandirán"],
            "conditional": [
                "blandiría",
                "blandirías",
                "blandiría",
                "blandiríamos",
                "blandiríais",
                "blandirían",
            ],
        },
    },
    "argüir": {
        "tier": "rare",
        "tenses": {
            "present": ["arguyo", "arguyes", "arguye", "arguimos", "arguís", "arguyen"],
            "preterite": ["argüí", "argüiste", "arguyó", "arguimos", "argüisteis", "arguyeron"],
            "imperfect": ["argüía", "argüías", "argüía", "arguíamos", "argüíais", "argüían"],
            "future": ["argüiré", "argüirás", "argüirá", "argüiremos", "argüiréis", "argüirán"],
            "conditional": [
                "argüiría",
                "argüirías",
                "argüiría",
                "argüiríamos",
                "argüiríais",
                "argüirían",
            ],
        },
    },
}


@dataclass(frozen=True)
class ParadigmCase:
    id: str
    lemma: str
    tier: str
    tense: str
    expected: list[str]
    prompt: str


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _tokenize_spanish(text: str) -> list[str]:
    text = _strip_thinking(text)
    return re.findall(r"[\w\u00C0-\u024F]+", text, flags=re.UNICODE)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


PROMPT_VERSION = "explicit_v1"

TENSE_PHRASE: dict[str, str] = {
    "present": "present indicative",
    "preterite": "preterite (pretérito indefinido) indicative",
    "imperfect": "imperfect indicative",
    "future": "simple future indicative",
    "conditional": "conditional indicative",
}


def build_prompt(lemma: str, tense: str) -> str:
    tense_label = TENSE_PHRASE.get(tense, tense)
    return (
        f'Conjugate the Spanish verb "{lemma}" in the {tense_label}.\n'
        "List all six forms for: yo, tú, él/ella, nosotros, vosotros, ellos.\n"
        "Reply with only the six conjugated verb forms, one per line."
    )


def build_cases(lemmas: list[str] | None = None) -> list[ParadigmCase]:
    lemmas = lemmas or list(PARADIGMS)
    cases: list[ParadigmCase] = []
    for lemma in lemmas:
        meta = PARADIGMS[lemma]
        for tense in TENSES:
            cases.append(
                ParadigmCase(
                    id=f"{lemma}__{tense}",
                    lemma=lemma,
                    tier=meta["tier"],
                    tense=tense,
                    expected=meta["tenses"][tense],
                    prompt=build_prompt(lemma, tense),
                )
            )
    return cases


def complete(model_id: str, prompt: str, *, temperature: float) -> str:
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


def score_paradigm(case: ParadigmCase, raw: str) -> dict[str, Any]:
    tokens = [_normalize(t) for t in _tokenize_spanish(raw)]
    token_set = set(tokens)
    per_person: list[dict[str, Any]] = []
    hits = 0
    for label, gold in zip(PERSON_LABELS, case.expected, strict=True):
        gold_norm = _normalize(gold)
        found = gold_norm in token_set
        if found:
            hits += 1
        per_person.append(
            {
                "person": label,
                "expected": gold,
                "found": found,
            }
        )
    return {
        "raw": raw.strip(),
        "forms_found": hits,
        "forms_total": len(case.expected),
        "form_recall": round(hits / len(case.expected), 4),
        "per_person": per_person,
        "missing": [p["expected"] for p in per_person if not p["found"]],
    }


def _rate(rows: list[dict[str, Any]], *, tier: str | None = None) -> dict[str, Any]:
    filtered = rows
    if tier:
        filtered = [r for r in filtered if r["case"]["tier"] == tier]
    n_forms = sum(r["forms_total"] for r in filtered)
    k_forms = sum(r["forms_found"] for r in filtered)
    n_cases = len(filtered)
    lo, hi = wilson_ci(k_forms, n_forms)
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


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}}
    for key, block in data["by_model"].items():
        rows = block["results"]
        out["per_model"][key] = {
            "overall": _rate(rows),
            "common_regular": _rate(rows, tier="common_regular"),
            "common_irregular": _rate(rows, tier="common_irregular"),
            "rare": _rate(rows, tier="rare"),
            "by_verb": {},
            "by_tense": {t: _rate([r for r in rows if r["case"]["tense"] == t]) for t in TENSES},
        }
        for lemma in PARADIGMS:
            verb_rows = [r for r in rows if r["case"]["lemma"] == lemma]
            out["per_model"][key]["by_verb"][lemma] = _rate(verb_rows)
    return out


def run_spike(
    model_keys: list[str],
    *,
    lemmas: list[str] | None,
    temperature: float,
) -> dict[str, Any]:
    cases = build_cases(lemmas)
    results: dict[str, Any] = {
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "temperature": temperature,
        "prompt_version": PROMPT_VERSION,
        "prompt_template": (
            'Conjugate "{lemma}" in {tense} indicative; '
            "list yo/tú/él/nosotros/vosotros/ellos forms, one per line."
        ),
        "verbs": list(lemmas or PARADIGMS.keys()),
        "tenses": list(TENSES),
        "paradigms": PARADIGMS,
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
            scored = score_paradigm(case, raw)
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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Spanish paradigm spike (minimal prompt, Qwen ladder)")
    parser.add_argument("--models", nargs="+", choices=list(QWEN_MODELS), default=list(QWEN_MODELS))
    parser.add_argument("--verbs", nargs="+", choices=list(PARADIGMS), default=list(PARADIGMS))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Results JSON path (default: docs/spike-results/eval_spanish_paradigm_qwen_spike_results.json)",
    )
    args = parser.parse_args()

    if args.dry_run:
        cases = build_cases(args.verbs)
        for c in cases:
            print(f"{c.id}: {c.prompt!r}")
        print(f"\n{len(cases)} calls × {len(args.models)} models")
        return

    print(
        f"Spanish paradigm spike: verbs={args.verbs}, "
        f"{len(build_cases(args.verbs))} calls, models={args.models}, temp={args.temperature}"
    )
    data = run_spike(args.models, lemmas=args.verbs, temperature=args.temperature)

    out_path = args.output or (
        Path(__file__).resolve().parents[2] / "docs" / "spike-results" / "eval_spanish_paradigm_qwen_spike_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
