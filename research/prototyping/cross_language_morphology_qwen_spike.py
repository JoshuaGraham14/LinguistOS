#!/usr/bin/env python3
"""Cross-language morphology spike — fair English vs Spanish (Exp 1B + 2B).

Re-runs the isolation-probe idea from Experiments 1 and 2, but with the
asymmetries removed so the cross-language claim is defensible:

  * Same number of probes per verb in both languages
    (past tense 1st singular + past participle).
  * Same prompt template, parametrised by language only.
  * Matched tier sizes (7 common + 7 rare per language = 28 probes each).
  * Curated gold from RAE/OED with accepted alternates listed.

This is the controlled counterpart to ``english_rare_verbs_qwen_spike.py``
and ``spanish_verbs_qwen_spike.py``. It does NOT replace them — the
originals stay as the historical record of the first diagnostic pass.

Output: ``docs/spike-results/eval_cross_language_morphology_qwen_v2_results.json``

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Status:      Diagnostic spike (Experiment 1B + 2B). Not run through
             ``research.run_experiment`` or the DB pipeline. Isolation
             probes (one-word answers, no sentence generation) sit
             outside the sentence-evaluator stack by design.

Run:         python3 -m research.prototyping.cross_language_morphology_qwen_spike
             (run from repo root; no CLI flags required)

Output:      docs/spike-results/eval_cross_language_morphology_qwen_v2_results.json

Stimuli:     14 English verbs + 14 Spanish verbs (7 common + 7 rare per
             language), hard-coded below. 2 probes per verb
             (past tense 1st singular, past participle) =
             28 probes per language, 56 total per model.

Models:      Qwen/Qwen2.5-0.5B-Instruct, Qwen/Qwen3-1.7B,
             Qwen/Qwen3-4B-Instruct-2507 (HuggingFace, MPS or CPU).

Decoding:    Greedy (temperature=0, do_sample=False), max_new_tokens=32,
             one sample per probe. Qwen3 thinking mode disabled.
             Deterministic; no seed required.

Scoring:     Unicode NFC + casefold exact match against the gold set
             (primary form plus any dictionary-listed alternates).

Gold source: English forms cross-checked against OED / Merriam-Webster;
             Spanish forms cross-checked against the RAE / SpanishDict
             paradigms. ``henchir`` 1st sg preterite is ``henchí`` (not
             ``hencho``, which is not the 1st sg preterite — lesson
             from the niche benchmark bug, June 2026).
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

# Probe taxonomy. Two probes per verb in every language; the form labels
# are identical across languages so the prompt is structurally matched.
PROBES = ("past_tense_1sg", "past_participle")

FORM_LABELS: dict[str, dict[str, str]] = {
    "English": {
        "past_tense_1sg": "simple past tense (first person singular, 'I')",
        "past_participle": "past participle",
    },
    "Spanish": {
        # Disambiguate the Spanish past tense as preterite ('pretérito
        # indefinido') so the model cannot legally answer with the
        # imperfect; this matches the English 'simple past'.
        "past_tense_1sg": (
            "simple past tense, preterite (pretérito indefinido), "
            "first person singular ('yo')"
        ),
        "past_participle": "past participle (participio pasado)",
    },
}


@dataclass(frozen=True)
class VerbEntry:
    lemma: str
    gloss: str
    tier: str  # common | rare
    forms: dict[str, list[str]] = field(default_factory=dict)
    notes: str = ""


# 7 common + 7 rare per language. Forms list primary + accepted alternates.

ENGLISH_VERBS: list[VerbEntry] = [
    # Common irregular ────────────────────────────────────────────────────
    VerbEntry(
        lemma="go", gloss="to move from one place to another", tier="common",
        forms={"past_tense_1sg": ["went"], "past_participle": ["gone"]},
    ),
    VerbEntry(
        lemma="see", gloss="to perceive with the eyes", tier="common",
        forms={"past_tense_1sg": ["saw"], "past_participle": ["seen"]},
    ),
    VerbEntry(
        lemma="come", gloss="to move toward the speaker", tier="common",
        forms={"past_tense_1sg": ["came"], "past_participle": ["come"]},
    ),
    VerbEntry(
        lemma="take", gloss="to lay hold of with the hand", tier="common",
        forms={"past_tense_1sg": ["took"], "past_participle": ["taken"]},
    ),
    VerbEntry(
        lemma="give", gloss="to hand over to someone", tier="common",
        forms={"past_tense_1sg": ["gave"], "past_participle": ["given"]},
    ),
    VerbEntry(
        lemma="know", gloss="to be aware of through observation", tier="common",
        forms={"past_tense_1sg": ["knew"], "past_participle": ["known"]},
    ),
    VerbEntry(
        lemma="write", gloss="to mark letters or symbols on a surface", tier="common",
        forms={"past_tense_1sg": ["wrote"], "past_participle": ["written"]},
    ),
    # Rare / literary / archaic ────────────────────────────────────────────
    VerbEntry(
        lemma="gainsay", gloss="to deny or contradict", tier="rare",
        forms={"past_tense_1sg": ["gainsaid"], "past_participle": ["gainsaid"]},
    ),
    VerbEntry(
        lemma="beseech", gloss="to implore or beg earnestly", tier="rare",
        forms={
            "past_tense_1sg": ["besought", "beseeched"],
            "past_participle": ["besought", "beseeched"],
        },
    ),
    VerbEntry(
        lemma="smite", gloss="to strike heavily", tier="rare",
        forms={"past_tense_1sg": ["smote"], "past_participle": ["smitten", "smote"]},
    ),
    VerbEntry(
        lemma="shrive", gloss="to hear confession and grant absolution", tier="rare",
        forms={
            "past_tense_1sg": ["shrove", "shrived"],
            "past_participle": ["shriven", "shrived"],
        },
    ),
    VerbEntry(
        lemma="gird", gloss="to encircle or prepare oneself", tier="rare",
        forms={
            "past_tense_1sg": ["girt", "girded"],
            "past_participle": ["girt", "girded"],
        },
    ),
    VerbEntry(
        lemma="forswear", gloss="to renounce or perjure oneself", tier="rare",
        forms={"past_tense_1sg": ["forswore"], "past_participle": ["forsworn"]},
    ),
    VerbEntry(
        lemma="clothe", gloss="to dress or provide with clothing", tier="rare",
        forms={
            "past_tense_1sg": ["clad", "clothed"],
            "past_participle": ["clad", "clothed"],
        },
    ),
]


SPANISH_VERBS: list[VerbEntry] = [
    # Common ──────────────────────────────────────────────────────────────
    VerbEntry(
        lemma="hablar", gloss="to speak", tier="common",
        forms={"past_tense_1sg": ["hablé"], "past_participle": ["hablado"]},
    ),
    VerbEntry(
        lemma="comer", gloss="to eat", tier="common",
        forms={"past_tense_1sg": ["comí"], "past_participle": ["comido"]},
    ),
    VerbEntry(
        lemma="vivir", gloss="to live", tier="common",
        forms={"past_tense_1sg": ["viví"], "past_participle": ["vivido"]},
    ),
    VerbEntry(
        lemma="correr", gloss="to run", tier="common",
        forms={"past_tense_1sg": ["corrí"], "past_participle": ["corrido"]},
    ),
    VerbEntry(
        lemma="escribir", gloss="to write", tier="common",
        forms={"past_tense_1sg": ["escribí"], "past_participle": ["escrito"]},
    ),
    VerbEntry(
        lemma="tener", gloss="to have", tier="common",
        forms={"past_tense_1sg": ["tuve"], "past_participle": ["tenido"]},
    ),
    VerbEntry(
        lemma="hacer", gloss="to do; to make", tier="common",
        forms={"past_tense_1sg": ["hice"], "past_participle": ["hecho"]},
    ),
    # Rare ────────────────────────────────────────────────────────────────
    VerbEntry(
        lemma="henchir", gloss="to fill (literary)", tier="rare",
        forms={"past_tense_1sg": ["henchí"], "past_participle": ["henchido"]},
        notes="1st sg preterite is henchí; present 1st sg is hincho (e->i).",
    ),
    VerbEntry(
        lemma="argüir", gloss="to argue (formally)", tier="rare",
        forms={"past_tense_1sg": ["argüí"], "past_participle": ["argüido"]},
    ),
    VerbEntry(
        lemma="atestiguar", gloss="to testify", tier="rare",
        forms={"past_tense_1sg": ["atestigüé"], "past_participle": ["atestiguado"]},
    ),
    VerbEntry(
        lemma="menguar", gloss="to diminish", tier="rare",
        forms={"past_tense_1sg": ["mengüé"], "past_participle": ["menguado"]},
    ),
    VerbEntry(
        lemma="empalagar", gloss="to cloy; to sicken", tier="rare",
        forms={"past_tense_1sg": ["empalagué"], "past_participle": ["empalagado"]},
    ),
    VerbEntry(
        lemma="blandir", gloss="to brandish", tier="rare",
        forms={"past_tense_1sg": ["blandí"], "past_participle": ["blandido"]},
    ),
    VerbEntry(
        lemma="proferir", gloss="to utter (threats/insults)", tier="rare",
        forms={"past_tense_1sg": ["proferí"], "past_participle": ["proferido"]},
    ),
]


LANGUAGE_ENTRIES: dict[str, list[VerbEntry]] = {
    "English": ENGLISH_VERBS,
    "Spanish": SPANISH_VERBS,
}


@dataclass
class ProbeCase:
    id: str
    language: str
    lemma: str
    gloss: str
    tier: str
    probe: str
    form_label: str
    expected: list[str]
    prompt: str


# Identical user-prompt template across languages. Only the language name,
# form label, lemma, and gloss change — the morphological information
# requested (one inflected form, fixed person where applicable) is matched.
USER_TEMPLATE = (
    'What is the {form_label} of the {language} verb "{lemma}" '
    '(meaning: "{gloss}")? Reply with one word only.'
)


def _normalize(text: str) -> str:
    """NFC + casefold + edge-punct strip. Accent-preserving."""
    return unicodedata.normalize("NFC", text).strip(_EDGE_PUNCT).casefold()


def _first_token(text: str) -> str:
    cleaned = _strip_thinking(text).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response|respuesta)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    # Accept any unicode word char + apostrophe/hyphen.
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


def build_cases() -> list[ProbeCase]:
    cases: list[ProbeCase] = []
    for language, entries in LANGUAGE_ENTRIES.items():
        for entry in entries:
            for probe in PROBES:
                form_label = FORM_LABELS[language][probe]
                prompt = USER_TEMPLATE.format(
                    form_label=form_label,
                    language=language,
                    lemma=entry.lemma,
                    gloss=entry.gloss,
                )
                cases.append(
                    ProbeCase(
                        id=f"{language.lower()}__{entry.lemma}__{probe}",
                        language=language,
                        lemma=entry.lemma,
                        gloss=entry.gloss,
                        tier=entry.tier,
                        probe=probe,
                        form_label=form_label,
                        expected=entry.forms[probe],
                        prompt=prompt,
                    )
                )
    return cases


def _system_message(language: str) -> str:
    return (
        f"You are a precise {language} morphology assistant. "
        "Follow the instruction exactly. Give only the requested word."
    )


def complete(model_id: str, case: ProbeCase, *, temperature: float) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    messages = [
        {"role": "system", "content": _system_message(case.language)},
        {"role": "user", "content": case.prompt},
    ]
    template_kwargs: dict[str, Any] = {"add_generation_prompt": True, "tokenize": False}
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
        "infinitive_fallback": norm == lemma_norm,
    }


def _rate(rows: list[dict[str, Any]], **filters: str) -> dict[str, Any]:
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


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}}
    for key, block in data["by_model"].items():
        rows = block["results"]
        per_model: dict[str, Any] = {"overall": _rate(rows)}
        for lang in ("English", "Spanish"):
            per_model[f"{lang.lower()}_overall"] = _rate(rows, language=lang)
            for tier in ("common", "rare"):
                per_model[f"{lang.lower()}_{tier}"] = _rate(rows, language=lang, tier=tier)
                for probe in PROBES:
                    per_model[f"{lang.lower()}_{tier}_{probe}"] = _rate(
                        rows, language=lang, tier=tier, probe=probe
                    )
        per_model["failures"] = [
            {
                "id": r["case"]["id"],
                "expected": r["case"]["expected"],
                "got": r["parsed_token"],
                "raw": r["raw"],
            }
            for r in rows
            if not r["correct"]
        ]
        out["per_model"][key] = per_model
    return out


def run_spike(model_keys: list[str], *, temperature: float) -> dict[str, Any]:
    cases = build_cases()
    payload: dict[str, Any] = {
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "temperature": temperature,
        "probes": list(PROBES),
        "form_labels": FORM_LABELS,
        "user_template": USER_TEMPLATE,
        "verb_entries": {
            "English": [asdict(v) for v in ENGLISH_VERBS],
            "Spanish": [asdict(v) for v in SPANISH_VERBS],
        },
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
            raw = complete(model_id, case, temperature=temperature)
            scored = score_response(case, raw)
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
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross-language morphology spike (Exp 1B + 2B): "
        "matched English vs Spanish isolation probes on the Qwen ladder.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(QWEN_MODELS),
        help="Which Qwen checkpoints to run (default: all three).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="0 = greedy decoding (recommended; deterministic).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print every probe and exit without loading models.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: docs/spike-results/...).",
    )
    args = parser.parse_args()

    if args.dry_run:
        cases = build_cases()
        print(f"{len(cases)} probes:")
        for c in cases:
            print(f"  [{c.language}/{c.tier}/{c.probe}] {c.lemma} -> {c.expected}")
            print(f"    prompt: {c.prompt}")
        return

    data = run_spike(args.models, temperature=args.temperature)
    out_path = args.output or (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "spike-results"
        / "eval_cross_language_morphology_qwen_v2_results.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
