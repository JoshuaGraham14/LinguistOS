#!/usr/bin/env python3
"""Diagnostic 1B — morphology verification, yes/no judge (frequency-validated).

Diagnostic 1B is the **verify** arm of Diagnostic 1 (isolation morphology).
The paired **generate** arm is Diagnostic 1A
(``diagnostic_1_freq_validated_isolation_qwen_spike``).

Loads stimuli from ``manifest_diagnostic_1_n25.csv`` (same verbs/probes as
Diagnostic 1A). Each trial presents lemma + form label + candidate surface form;
the model must reply yes/no.

Two conditions per (verb, probe):
  * gold — correct form (expected accept)
  * foil — incorrect form (expected reject)

Foil types (first valid option wins):
  1. regularization — regular-paradigm form when gold is irregular
  2. wrong_tense — present / imperfect / wrong person for the probed slot
  3. infinitive_echo — lemma as candidate

Output: ``docs/spike-results/eval_diagnostic_1b_n25_verification_qwen_results.json``

----------------------------------------------------------------------
REPRODUCIBILITY
----------------------------------------------------------------------
Status:      Diagnostic 1B. Not run through ``research.run_experiment`` or the DB.

Run:         python3 -m research.prototyping.diagnostic_1b_morphology_verification_qwen_spike
             python3 -m research.prototyping.diagnostic_1b_morphology_verification_qwen_spike --dry-run
             python3 -m research.prototyping.diagnostic_1b_morphology_verification_qwen_spike \\
                 --models qwen17b --limit 8

Manifest:    research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_1_n25.csv
Registry:    research/diagnostics/registry.yaml
Models:      Qwen/Qwen3-0.6B, Qwen/Qwen3-1.7B, Qwen/Qwen3-4B (thinking disabled)
Decoding:    Greedy (temperature=0), max_new_tokens=16
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

from research.evaluation.lexicon.en_gold_forms import en_past_and_participle
from research.evaluation.lexicon.frequency import (
    _actual_es_form,
    _en_regular_forms,
    _regular_es_form,
)
from research.generation.baseline_hf import _is_qwen3, _load_model, _strip_thinking, unload_model

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"

QWEN_MODELS: dict[str, str] = {
    "qwen06b": "Qwen/Qwen3-0.6B",
    "qwen17b": "Qwen/Qwen3-1.7B",
    "qwen4b": "Qwen/Qwen3-4B",
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
    / "eval_diagnostic_1b_n25_verification_qwen_results.json"
)

DIAGNOSTIC_ID = "diagnostic_1b"
DIAGNOSTIC_NUMBER = "1B"
DIAGNOSTIC_TITLE = "Cross-language morphology isolation (verification)"
DIAGNOSTIC_LABEL = "Diagnostic 1B — morphology verification, yes/no judge (frequency-validated)"
DIAGNOSTIC_SERIES = "diagnostic_1"

LangName = Literal["English", "Spanish"]
LangCode = Literal["en", "es"]
ProbeId = Literal["past_tense_1sg", "past_participle"]
Condition = Literal["gold", "foil"]
FoilType = Literal["regularization", "wrong_tense", "infinitive_echo"]

PROBES: tuple[ProbeId, ...] = ("past_tense_1sg", "past_participle")
CONDITIONS: tuple[Condition, ...] = ("gold", "foil")

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
    'Is "{candidate}" a correct {form_label} of the {language} verb "{lemma}"? '
    "Reply yes or no only."
)

USER_TEMPLATE_ES = (
    '¿Es "{candidate}" una forma correcta de {form_label} del verbo '
    '{language} "{lemma}"? Responde solo sí o no.'
)

PROMPT_VARIANTS: dict[str, str] = {
    "default": USER_TEMPLATE,
    "es_native": USER_TEMPLATE_ES,
}


@dataclass
class VerificationCase:
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
    condition: Condition
    foil_type: str | None
    candidate: str
    expected_accept: bool
    gold_forms: list[str]
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


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip(_EDGE_PUNCT).casefold()


def _gold_norms(forms: list[str]) -> set[str]:
    return {_normalize(f) for f in forms}


def _is_gold_form(candidate: str, gold_forms: list[str]) -> bool:
    return _normalize(candidate) in _gold_norms(gold_forms)


def _regular_es_participle(lemma: str) -> str | None:
    if len(lemma) < 3:
        return None
    ending_class = lemma[-2:]
    if ending_class == "ar":
        return f"{lemma[:-2]}ado"
    if ending_class in ("er", "ir"):
        return f"{lemma[:-2]}ido"
    return None


def _en_present_3sg(lemma: str) -> str:
    stem = lemma.lower()
    if stem.endswith(("s", "x", "z", "ch", "sh")):
        return f"{stem}es"
    if stem.endswith("y") and len(stem) >= 2 and stem[-2] not in "aeiou":
        return f"{stem[:-1]}ies"
    return f"{stem}s"


def _foil_candidates(
    row: dict[str, str],
    probe: ProbeId,
    gold_forms: list[str],
) -> list[tuple[FoilType, str]]:
    lang_code = row["lang"]
    lemma = row["verb"]
    gold_set = _gold_norms(gold_forms)
    out: list[tuple[FoilType, str]] = []

    def add(foil_type: FoilType, form: str | None) -> None:
        if not form:
            return
        if _normalize(form) in gold_set:
            return
        if any(_normalize(form) == _normalize(c) for _, c in out):
            return
        out.append((foil_type, form))

    if probe == "past_tense_1sg":
        if lang_code == "es":
            add("regularization", _regular_es_form(lemma, "preterite", "1st", "singular"))
            add("wrong_tense", _actual_es_form(lemma, "present", "1st", "singular"))
            add("wrong_tense", _actual_es_form(lemma, "imperfect", "1st", "singular"))
            add("wrong_tense", _actual_es_form(lemma, "preterite", "3rd", "singular"))
        else:
            reg_forms = _en_regular_forms(lemma)
            if len(reg_forms) >= 3:
                add("regularization", reg_forms[2])
            add("wrong_tense", lemma)
            add("wrong_tense", _en_present_3sg(lemma))
    else:
        if lang_code == "es":
            add("regularization", _regular_es_participle(lemma))
            add("wrong_tense", _actual_es_form(lemma, "preterite", "1st", "singular"))
            add("wrong_tense", _actual_es_form(lemma, "present", "1st", "singular"))
        else:
            reg_forms = _en_regular_forms(lemma)
            if len(reg_forms) >= 3:
                add("regularization", reg_forms[2])
            past_forms, _ = en_past_and_participle(lemma)
            for past in past_forms:
                add("wrong_tense", past)
            add("wrong_tense", lemma)

    add("infinitive_echo", lemma)
    return out


def _pick_foil(
    row: dict[str, str],
    probe: ProbeId,
    gold_forms: list[str],
) -> tuple[FoilType, str]:
    candidates = _foil_candidates(row, probe, gold_forms)
    if not candidates:
        raise ValueError(
            f"no foil for {row['lang']}:{row['verb']}:{probe} (gold={gold_forms})"
        )
    return candidates[0]


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_cases(
    manifest_rows: list[dict[str, str]],
    *,
    languages: set[LangCode] | None = None,
    probes: tuple[ProbeId, ...] = PROBES,
    conditions: tuple[Condition, ...] = CONDITIONS,
    limit: int | None = None,
    prompt_variant: str = "default",
) -> list[VerificationCase]:
    cases: list[VerificationCase] = []
    rows = manifest_rows
    if languages:
        rows = [r for r in rows if r["lang"] in languages]

    for row in rows:
        lang_code = row["lang"]  # type: ignore[assignment]
        if lang_code not in LANG_CODE_TO_NAME:
            raise ValueError(f"unsupported lang code {lang_code!r}")
        language = LANG_CODE_TO_NAME[lang_code]  # type: ignore[index]

        for probe in probes:
            gold = _gold_forms(row, probe)
            form_label = FORM_LABELS[language][probe]
            foil_type, foil_form = _pick_foil(row, probe, gold)

            for condition in conditions:
                if condition == "gold":
                    candidate = gold[0]
                    foil_t: str | None = None
                    expected_accept = True
                else:
                    candidate = foil_form
                    foil_t = foil_type
                    expected_accept = False

                if prompt_variant == "es_native" and lang_code == "es":
                    prompt = USER_TEMPLATE_ES.format(
                        candidate=candidate,
                        form_label=form_label,
                        language=language,
                        lemma=row["verb"],
                    )
                else:
                    prompt = USER_TEMPLATE.format(
                        candidate=candidate,
                        form_label=form_label,
                        language=language,
                        lemma=row["verb"],
                    )

                cases.append(
                    VerificationCase(
                        id=f"{lang_code}__{row['verb']}__{probe}__{condition}",
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
                        condition=condition,
                        foil_type=foil_t,
                        candidate=candidate,
                        expected_accept=expected_accept,
                        gold_forms=gold,
                        prompt=prompt,
                    )
                )

    if limit is not None:
        cases = cases[:limit]
    return cases


_YES_RE = re.compile(
    r"\b(yes|yeah|yep|correct|true|right|affirmative|sí|si|afirmativo)\b",
    re.I | re.UNICODE,
)
_NO_RE = re.compile(
    r"\b(no|nope|incorrect|false|wrong|negative|negativo)\b",
    re.I | re.UNICODE,
)


def _parse_yes_no(raw: str) -> bool | None:
    cleaned = _strip_thinking(raw).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response|respuesta)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    if not cleaned:
        return None

    first = re.search(r"[\w']+", cleaned, flags=re.UNICODE)
    token = first.group(0) if first else cleaned
    token_cf = token.casefold()

    if token_cf in {"yes", "yeah", "yep", "correct", "true", "right", "sí", "si"}:
        return True
    if token_cf in {"no", "nope", "incorrect", "false", "wrong"}:
        return False

    yes_hit = bool(_YES_RE.search(cleaned))
    no_hit = bool(_NO_RE.search(cleaned))
    if yes_hit and not no_hit:
        return True
    if no_hit and not yes_hit:
        return False
    return None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _system_message(language: LangName) -> str:
    return (
        f"You are a precise {language} morphology assistant. "
        "Judge whether the proposed verb form is correct for the requested slot. "
        "Reply with only yes or no."
    )


def complete(model_id: str, case: VerificationCase, *, temperature: float) -> str:
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
        "max_new_tokens": 16,
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


def score_response(case: VerificationCase, raw: str) -> dict[str, Any]:
    parsed = _parse_yes_no(raw)
    return {
        "raw": raw.strip(),
        "parsed_yes": parsed,
        "correct": parsed is not None and parsed == case.expected_accept,
        "unparseable": parsed is None,
    }


def _rate(rows: list[dict[str, Any]], **filters: Any) -> dict[str, Any]:
    filtered = [
        r for r in rows
        if all(r["case"].get(k) == v for k, v in filters.items())
    ]
    n = len(filtered)
    k = sum(1 for r in filtered if r["correct"])
    lo, hi = wilson_ci(k, n)
    unparseable = sum(1 for r in filtered if r["unparseable"])
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4) if n else None,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
        "unparseable": unparseable,
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
        per_model: dict[str, Any] = {
            "overall": _rate(rows),
            "gold_accept": _rate(rows, condition="gold"),
            "foil_reject": _rate(rows, condition="foil"),
        }
        for lang_code in LANG_CODE_TO_NAME:
            per_model[f"{lang_code}_overall"] = _rate(rows, lang_code=lang_code)
            per_model[f"{lang_code}_gold_accept"] = _rate(rows, lang_code=lang_code, condition="gold")
            per_model[f"{lang_code}_foil_reject"] = _rate(rows, lang_code=lang_code, condition="foil")
            for probe in PROBES:
                per_model[f"{lang_code}_{probe}"] = _rate(rows, lang_code=lang_code, probe=probe)
                per_model[f"{lang_code}_{probe}_gold"] = _rate(
                    rows, lang_code=lang_code, probe=probe, condition="gold"
                )
                per_model[f"{lang_code}_{probe}_foil"] = _rate(
                    rows, lang_code=lang_code, probe=probe, condition="foil"
                )
            for cell in cells:
                per_model[f"{lang_code}_{cell}"] = _rate(rows, lang_code=lang_code, cell_id=cell)
        for foil_type in ("regularization", "wrong_tense", "infinitive_echo"):
            per_model[f"foil_{foil_type}"] = _rate(rows, condition="foil", foil_type=foil_type)
        per_model["failures"] = [
            {
                "id": r["case"]["id"],
                "condition": r["case"]["condition"],
                "foil_type": r["case"]["foil_type"],
                "candidate": r["case"]["candidate"],
                "expected_accept": r["case"]["expected_accept"],
                "parsed_yes": r["parsed_yes"],
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
    cases: list[VerificationCase],
    model_keys: list[str],
    *,
    temperature: float,
    manifest_path: Path,
    manifest_rows: list[dict[str, str]],
    output_path: Path | None = None,
    prompt_variant: str = "default",
    resume: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    if resume and output_path is not None and output_path.is_file():
        with output_path.open(encoding="utf-8") as f:
            payload = json.load(f)
        done = set(payload.get("by_model", {}))
        model_keys = [k for k in model_keys if k not in done]
        if not model_keys:
            print(f"All requested models already in {output_path}", flush=True)
            return payload
        print(f"Resuming; remaining models: {model_keys}", flush=True)

    if payload is None:
        foil_counts: dict[str, int] = {}
        for c in cases:
            if c.condition == "foil" and c.foil_type:
                foil_counts[c.foil_type] = foil_counts.get(c.foil_type, 0) + 1
        payload = {
            "diagnostic_id": DIAGNOSTIC_ID,
            "diagnostic_number": DIAGNOSTIC_NUMBER,
            "diagnostic_title": DIAGNOSTIC_TITLE,
            "diagnostic_label": DIAGNOSTIC_LABEL,
            "diagnostic_series": DIAGNOSTIC_SERIES,
            "related_diagnostics": ["diagnostic_1a"],
            "manifest_path": str(manifest_path),
            "manifest_seed": manifest_rows[0].get("seed") if manifest_rows else None,
            "n_verbs": len(manifest_rows),
            "n_trials": len(cases),
            "n_trials_per_model_expected": len(cases),
            "models": {k: QWEN_MODELS[k] for k in model_keys},
            "temperature": temperature,
            "probes": list(PROBES),
            "conditions": list(CONDITIONS),
            "foil_type_counts": foil_counts,
            "form_labels": FORM_LABELS,
            "prompt_variant": prompt_variant,
            "user_template": PROMPT_VARIANTS[prompt_variant],
            "by_model": {},
        }
    else:
        payload["models"] = {
            **payload.get("models", {}),
            **{k: QWEN_MODELS[k] for k in model_keys},
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
        if output_path is not None:
            _save_payload(payload, output_path)
            print(f"  checkpoint saved → {output_path}", flush=True)
        unload_model(model_id)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{DIAGNOSTIC_LABEL} — Qwen ladder verification probe from manifest.",
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
        "--conditions",
        nargs="+",
        choices=list(CONDITIONS),
        default=list(CONDITIONS),
        help="Gold and/or foil trials (default: both).",
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
        help="Run only the first N trials (smoke test).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print trials and exit without loading models.",
    )
    parser.add_argument(
        "--prompt-variant",
        choices=list(PROMPT_VARIANTS),
        default="default",
        help="Prompt template variant.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip models already present in --output (for cluster retries).",
    )
    args = parser.parse_args()

    manifest_rows = load_manifest(args.manifest)
    probe_tuple = tuple(args.probes)  # type: ignore[assignment]
    condition_tuple = tuple(args.conditions)  # type: ignore[assignment]
    cases = build_cases(
        manifest_rows,
        languages=set(args.lang),
        probes=probe_tuple,
        conditions=condition_tuple,
        limit=args.limit,
        prompt_variant=args.prompt_variant,
    )

    if args.dry_run:
        foil_counts: dict[str, int] = {}
        for c in cases:
            if c.foil_type:
                foil_counts[c.foil_type] = foil_counts.get(c.foil_type, 0) + 1
        print(f"{DIAGNOSTIC_LABEL}")
        print(f"Manifest: {args.manifest} ({len(manifest_rows)} verbs)")
        print(f"Trials to run: {len(cases)}")
        print(f"Foil type counts: {foil_counts}")
        for c in cases[:24]:
            accept = "accept" if c.expected_accept else "reject"
            foil = f" [{c.foil_type}]" if c.foil_type else ""
            print(
                f"  [{c.lang_code}/{c.cell_id}/{c.probe}/{c.condition}{foil}] "
                f"{c.lemma} ? {c.candidate!r} → {accept}"
            )
        if len(cases) > 24:
            print(f"  ... and {len(cases) - 24} more")
        return

    data = run_spike(
        cases,
        args.models,
        temperature=args.temperature,
        manifest_path=args.manifest,
        manifest_rows=manifest_rows,
        output_path=args.output,
        prompt_variant=args.prompt_variant,
        resume=args.resume,
    )
    _save_payload(data, args.output)
    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {args.output}")


if __name__ == "__main__":
    main()
