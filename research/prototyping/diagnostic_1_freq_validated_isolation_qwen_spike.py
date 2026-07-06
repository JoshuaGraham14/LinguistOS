#!/usr/bin/env python3
"""Diagnostic 1 — cross-language morphology isolation (frequency-validated).

Loads stimuli from ``research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_1_n25.csv``
(300 verbs: 150 English + 150 Spanish, 25 per frequency×irregularity cell).

Part of the **Diagnostics** track (rigorous, census-grounded runs). Numbering is
independent of the original exploratory Experiments 1–10; see
``research/diagnostics/registry.yaml``.

Design:
  * 2 probes per verb: past tense 1sg + past participle (both languages).
  * One prompt template, parametrised by language + form label only.
  * Greedy decoding, Qwen3 0.6B / 1.7B / 4B ladder (same model family).

Output: ``docs/spike-results/eval_diagnostic_1_isolation_qwen_results.json``

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Status:      Diagnostic 1. Not run through ``research.run_experiment`` or the DB.

Run:         python3 -m research.prototyping.diagnostic_1_freq_validated_isolation_qwen_spike
             python3 -m research.prototyping.diagnostic_1_freq_validated_isolation_qwen_spike --dry-run
             python3 -m research.prototyping.diagnostic_1_freq_validated_isolation_qwen_spike \\
                 --models qwen06b --limit 4

Manifest:    research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_1_n25.csv
Legacy n=10: research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_1_n10.csv
Registry:    research/diagnostics/registry.yaml
Models:      Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B (thinking disabled)
Decoding:    Greedy (temperature=0), max_new_tokens=32
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

from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"

QWEN_MODELS: dict[str, str] = {
    "qwen06b": "Qwen/Qwen3-0.6B",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B",
    # Legacy key (Qwen2.5); kept for reproducing older spikes only.
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
}

DEFAULT_MODEL_KEYS: tuple[str, ...] = ("qwen06b", "qwen17b", "qwen4b")

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_1_n25.csv"
)

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spike-results"
    / "eval_diagnostic_1_isolation_qwen_results.json"
)

DIAGNOSTIC_ID = "diagnostic_1"
DIAGNOSTIC_NUMBER = 1
DIAGNOSTIC_TITLE = "Cross-language morphology isolation"
DIAGNOSTIC_LABEL = "Diagnostic 1 — cross-language morphology isolation (frequency-validated)"

LangName = Literal["English", "Spanish"]
LangCode = Literal["en", "es"]
ProbeId = Literal["past_tense_1sg", "past_participle"]

PROBES: tuple[ProbeId, ...] = ("past_tense_1sg", "past_participle")

LANG_CODE_TO_NAME: dict[LangCode, LangName] = {"en": "English", "es": "Spanish"}

FORM_LABELS: dict[LangName, dict[ProbeId, str]] = {
    "English": {
        "past_tense_1sg": "simple past tense (first person singular, 'I')",
        "past_participle": "past participle",
    },
    "Spanish": {
        "past_tense_1sg": (
            "simple past tense, preterite (pretérito indefinido), "
            "first person singular ('yo')"
        ),
        "past_participle": "past participle (participio pasado)",
    },
}

USER_TEMPLATE = (
    'What is the {form_label} of the {language} verb "{lemma}"? '
    "Reply with one word only."
)

USER_TEMPLATE_VERB_ONLY = (
    'What is the {form_label} of the {language} verb "{lemma}"? '
    "Reply with the conjugated verb form only — one word, no pronoun or sentence."
)

PROMPT_VARIANTS: dict[str, str] = {
    "default": USER_TEMPLATE,
    "verb_only": USER_TEMPLATE_VERB_ONLY,
}


@dataclass
class ProbeCase:
    id: str
    language: LangName
    lang_code: LangCode
    lemma: str
    cell_id: str
    zipf: float
    tier: str
    irregular_probed: bool
    in_census: bool
    probe: ProbeId
    form_label: str
    expected: list[str]
    prompt: str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1"}


def _gold_forms(row: dict[str, str], probe: ProbeId) -> list[str]:
    if probe == "past_tense_1sg":
        primary, alts = row["gold_past_1sg"], row.get("gold_past_1sg_alts", "")
    else:
        primary, alts = row["gold_participle"], row.get("gold_participle_alts", "")
    forms = [primary]
    forms.extend(x for x in alts.split("|") if x)
    return forms


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_cases(
    manifest_rows: list[dict[str, str]],
    *,
    languages: set[LangCode] | None = None,
    probes: tuple[ProbeId, ...] = PROBES,
    limit: int | None = None,
    user_template: str = USER_TEMPLATE,
) -> list[ProbeCase]:
    cases: list[ProbeCase] = []
    rows = manifest_rows
    if languages:
        rows = [r for r in rows if r["lang"] in languages]

    for row in rows:
        lang_code = row["lang"]  # type: ignore[assignment]
        if lang_code not in LANG_CODE_TO_NAME:
            raise ValueError(f"unsupported lang code {lang_code!r}")
        language = LANG_CODE_TO_NAME[lang_code]  # type: ignore[index]

        for probe in probes:
            form_label = FORM_LABELS[language][probe]
            prompt = user_template.format(
                form_label=form_label,
                language=language,
                lemma=row["verb"],
            )
            cases.append(
                ProbeCase(
                    id=f"{lang_code}__{row['verb']}__{probe}",
                    language=language,
                    lang_code=lang_code,  # type: ignore[arg-type]
                    lemma=row["verb"],
                    cell_id=row["cell_id"],
                    zipf=float(row["zipf"]),
                    tier=row["tier"],
                    irregular_probed=_parse_bool(row["irregular_probed"]),
                    in_census=_parse_bool(row["in_census"]),
                    probe=probe,
                    form_label=form_label,
                    expected=_gold_forms(row, probe),
                    prompt=prompt,
                )
            )

    if limit is not None:
        cases = cases[:limit]
    return cases


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip(_EDGE_PUNCT).casefold()


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


def _system_message(language: LangName, *, prompt_variant: str = "default") -> str:
    if prompt_variant == "verb_only":
        return (
            f"You are a precise {language} morphology assistant. "
            "Output only the single conjugated verb form requested — never a pronoun or sentence."
        )
    return (
        f"You are a precise {language} morphology assistant. "
        "Follow the instruction exactly. Give only the requested word."
    )


def complete(
    model_id: str,
    case: ProbeCase,
    *,
    temperature: float,
    prompt_variant: str = "default",
) -> str:
    import torch

    tokenizer, model = _load_model(model_id)
    messages = [
        {"role": "system", "content": _system_message(case.language, prompt_variant=prompt_variant)},
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


def _rate(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
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
    cells = (
        "high_regular", "high_irregular",
        "mid_regular", "mid_irregular",
        "low_regular", "low_irregular",
    )
    for key, block in data["by_model"].items():
        rows = block["results"]
        per_model: dict[str, Any] = {"overall": _rate(rows)}
        for lang_code, lang_name in LANG_CODE_TO_NAME.items():
            per_model[f"{lang_code}_overall"] = _rate(rows, lang_code=lang_code)
            for cell in cells:
                per_model[f"{lang_code}_{cell}"] = _rate(rows, lang_code=lang_code, cell_id=cell)
            for probe in PROBES:
                per_model[f"{lang_code}_{probe}"] = _rate(rows, lang_code=lang_code, probe=probe)
        per_model["failures"] = [
            {
                "id": r["case"]["id"],
                "cell_id": r["case"]["cell_id"],
                "zipf": r["case"]["zipf"],
                "expected": r["case"]["expected"],
                "got": r["parsed_token"],
                "raw": r["raw"],
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


def run_spike(
    cases: list[ProbeCase],
    model_keys: list[str],
    *,
    temperature: float,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path | None = None,
    prompt_variant: str = "default",
    user_template: str = USER_TEMPLATE,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "diagnostic_id": DIAGNOSTIC_ID,
        "diagnostic_number": DIAGNOSTIC_NUMBER,
        "diagnostic_title": DIAGNOSTIC_TITLE,
        "diagnostic_label": DIAGNOSTIC_LABEL,
        "related_experiments": [1, 2, "1B", "2B"],
        "manifest_path": str(manifest_path),
        "manifest_seed": manifest_rows[0].get("seed") if manifest_rows else None,
        "n_verbs": len(manifest_rows),
        "n_probes": len(cases),
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "temperature": temperature,
        "probes": list({c.probe for c in cases}),
        "form_labels": FORM_LABELS,
        "prompt_variant": prompt_variant,
        "user_template": user_template,
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
            raw = complete(
                model_id, case, temperature=temperature, prompt_variant=prompt_variant
            )
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
        if output_path is not None:
            _save_payload(payload, output_path)
            print(f"  checkpoint saved → {output_path}", flush=True)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{DIAGNOSTIC_LABEL} — Qwen ladder isolation probe from manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Verb manifest CSV (default: manifest_diagnostic_1_n25.csv).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=list(DEFAULT_MODEL_KEYS),
        help="Which Qwen checkpoints to run (default: qwen06b qwen17b qwen4b).",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        choices=["en", "es"],
        default=["en", "es"],
        help="Languages to include (default: both).",
    )
    parser.add_argument(
        "--probes",
        nargs="+",
        choices=list(PROBES),
        default=list(PROBES),
        help="Which probe types to run (default: both).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="0 = greedy decoding (recommended).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N probes (smoke test).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print probes and exit without loading models.",
    )
    parser.add_argument(
        "--prompt-variant",
        choices=list(PROMPT_VARIANTS),
        default="default",
        help="Prompt template variant (default: one-word reply).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path.",
    )
    args = parser.parse_args()

    user_template = PROMPT_VARIANTS[args.prompt_variant]
    if args.output is None:
        if args.prompt_variant == "default":
            args.output = DEFAULT_OUTPUT
        else:
            args.output = (
                DEFAULT_OUTPUT.parent
                / f"eval_diagnostic_1_isolation_qwen_{args.prompt_variant}_prompt_results.json"
            )

    manifest_rows = load_manifest(args.manifest)
    probe_tuple = tuple(args.probes)  # type: ignore[assignment]
    cases = build_cases(
        manifest_rows,
        languages=set(args.lang),
        probes=probe_tuple,
        limit=args.limit,
        user_template=user_template,
    )

    if args.dry_run:
        print(f"{DIAGNOSTIC_LABEL}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} verbs)")
        print(f"Probes to run: {len(cases)}")
        for c in cases[:20]:
            print(f"  [{c.lang_code}/{c.cell_id}/{c.probe}] {c.lemma} -> {c.expected}")
        if len(cases) > 20:
            print(f"  ... and {len(cases) - 20} more")
        return

    data = run_spike(
        cases,
        args.models,
        temperature=args.temperature,
        manifest_path=args.manifest,
        manifest_rows=manifest_rows,
        output_path=args.output,
        prompt_variant=args.prompt_variant,
        user_template=user_template,
    )
    _save_payload(data, args.output)
    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {args.output}")


if __name__ == "__main__":
    main()
