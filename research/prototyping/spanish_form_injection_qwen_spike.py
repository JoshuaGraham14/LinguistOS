#!/usr/bin/env python3
"""Spanish form-injection spike (Experiment 6) -- Qwen 0.5B / 1.7B.

Builds directly on the Exp 5 prompt-ablation spike and asks one question:
does injecting the gold ``expected_form`` into the prompt close the
sentence-level binding gap that prompt engineering alone could not (Exp 5:
1.7B baseline ~30% EF, explicit ~58% EF)?

Four conditions per model:
  - baseline                : current ``build_prompt`` (same-session sanity control)
  - explicit                : ``build_prompt_explicit`` (Spanish overlay; no gold form)
  - form_injected           : ``build_prompt`` + gold expected form injected
  - form_injected_explicit  : ``build_prompt_explicit`` + gold expected form injected

Metrics captured per generated sentence:
  - expected_form_match (headline)
  - grammar_languagetool (LanguageTool grammar pass)
  - length_in_band       (token count within the requested band)

Results: ``docs/spike-results/eval_spanish_form_injection_qwen_results.json``
"""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.evaluation.sentence.length_in_band import LengthInBandEvaluator
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    parse_candidates_lenient,
)
from research.generation.languages import extract_constraints
from research.generation.prompt_builder import (
    build_prompt,
    build_prompt_explicit,
    language_display_name,
)

_BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
_DEFAULT_BENCHMARKS = ("spanish_basic",)

QWEN_MODELS: dict[str, str] = {
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen17b": "Qwen/Qwen3-1.7B",
}

# Reference EF rates from Exp 5 (same models, same benchmark, same prompts).
PRIOR_EF_REFERENCE: dict[str, dict[str, float]] = {
    "qwen05b": {"baseline": 0.00, "explicit": 0.049},
    "qwen17b": {"baseline": 0.30, "explicit": 0.58},
}

_EF = ExpectedFormMatchEvaluator()
_LEN = LengthInBandEvaluator()
_LT = LanguageToolGrammarEvaluator()


@dataclass
class BenchmarkCase:
    id: str
    benchmark: str
    keyword: str
    translation: str
    constraints: dict[str, Any]
    cefr_level: str | None = None
    expected_form: str | None = None


@dataclass
class ScoredCandidate:
    sentence: str
    translation: str
    expected_form: str | None
    ef_pass: bool
    length_in_band: bool | None
    token_count: int | None
    grammar_pass: bool | None
    grammar_match_count: int | None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def load_benchmark_cases(benchmark_names: list[str]) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for bm_name in benchmark_names:
        path = _BENCHMARKS_DIR / f"{bm_name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for i, cs in enumerate(data["constraint_sets"]):
            constraints = extract_constraints(cs)
            expected = cs.get("expected_form")
            if expected:
                constraints["expected_form"] = expected
            tense = cs.get("tense", "")
            person = cs.get("person", "")
            number = cs.get("number", "")
            case_id = f"{bm_name}__{cs['keyword']}__{tense}_{person}_{number}__{i}"
            cases.append(
                BenchmarkCase(
                    id=case_id,
                    benchmark=bm_name,
                    keyword=cs["keyword"],
                    translation=cs["translation"],
                    constraints=constraints,
                    cefr_level=cs.get("cefr_level"),
                    expected_form=expected,
                )
            )
    return cases


def _system_message(target_language: str = "es") -> str:
    lang = language_display_name(target_language)
    return f"You are a helpful {lang} language tutor. Always respond with valid JSON."


def hf_generate_batched(
    model_id: str,
    prompt: str,
    num_candidates: int,
    *,
    temperature: float = 0.7,
    target_language: str = "es",
) -> list[dict[str, str]]:
    """Batched HF generation with a custom user prompt (mirrors baseline_hf)."""
    gen = BaselineHFGenerator(model=model_id, temperature=temperature)
    system = _system_message(target_language)
    collected: list[dict[str, str]] = []
    for call_idx in range(BaselineHFGenerator.MAX_CALLS):
        remaining = num_candidates - len(collected)
        if remaining <= 0:
            break
        max_new_tokens = min(80 * remaining + 200, 3072)
        raw = gen._call(prompt, system, max_new_tokens)
        cands, mode = parse_candidates_lenient(raw)
        print(
            f"      [hf call {call_idx + 1}] requested={remaining} "
            f"parsed={len(cands)} mode={mode}"
        )
        collected.extend(cands)
    return collected[:num_candidates]


# Prompt builders ------------------------------------------------------------

PromptBuilder = Callable[[BenchmarkCase], str]


def _build_baseline(case: BenchmarkCase, *, n: int, length: str) -> str:
    return build_prompt(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=n,
        sentence_length=length,
        cefr_level=case.cefr_level,
    )


def _build_explicit(case: BenchmarkCase, *, n: int, length: str) -> str:
    return build_prompt_explicit(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=n,
        sentence_length=length,
        cefr_level=case.cefr_level,
    )


def _build_form_injected(case: BenchmarkCase, *, n: int, length: str) -> str:
    return build_prompt(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=n,
        sentence_length=length,
        cefr_level=case.cefr_level,
        inject_expected_form=case.expected_form,
    )


def _build_form_injected_explicit(case: BenchmarkCase, *, n: int, length: str) -> str:
    return build_prompt_explicit(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=n,
        sentence_length=length,
        cefr_level=case.cefr_level,
        inject_expected_form=case.expected_form,
    )


CONDITION_BUILDERS: dict[str, Callable[..., str]] = {
    "baseline": _build_baseline,
    "explicit": _build_explicit,
    "form_injected": _build_form_injected,
    "form_injected_explicit": _build_form_injected_explicit,
}


# Scoring --------------------------------------------------------------------


def _score(
    sentence: str,
    translation: str,
    case: BenchmarkCase,
    *,
    sentence_length: str,
    run_grammar: bool,
) -> ScoredCandidate:
    constraints_for_eval = dict(case.constraints)
    constraints_for_eval.setdefault("sentence_length", sentence_length)
    constraints_for_eval.setdefault("target_language", "es")

    ef_res = _EF.evaluate(sentence, translation, constraints_for_eval)
    len_res = _LEN.evaluate(sentence, translation, constraints_for_eval)

    grammar_pass: bool | None = None
    grammar_match_count: int | None = None
    if run_grammar:
        try:
            lt_res = _LT.evaluate(sentence, translation, constraints_for_eval)
            grammar_pass = bool(lt_res.details.get("passed"))
            grammar_match_count = int(lt_res.details.get("match_count", 0))
        except Exception as exc:  # pragma: no cover - environment-dependent
            print(f"      [warn] LanguageTool failed on sentence: {exc}")

    return ScoredCandidate(
        sentence=sentence,
        translation=translation,
        expected_form=case.expected_form,
        ef_pass=bool(ef_res.details.get("passed")),
        length_in_band=bool(len_res.details.get("in_band")),
        token_count=int(len_res.details.get("token_count", 0)),
        grammar_pass=grammar_pass,
        grammar_match_count=grammar_match_count,
    )


# Per-condition runner -------------------------------------------------------


def run_condition_for_case(
    model_id: str,
    case: BenchmarkCase,
    *,
    condition: str,
    samples: int,
    temperature: float,
    sentence_length: str,
    run_grammar: bool,
) -> list[ScoredCandidate]:
    builder = CONDITION_BUILDERS[condition]
    prompt = builder(case, n=samples, length=sentence_length)
    raw_cands = hf_generate_batched(
        model_id,
        prompt,
        samples,
        temperature=temperature,
    )
    scored: list[ScoredCandidate] = []
    for cand in raw_cands:
        scored.append(
            _score(
                cand["sentence"],
                cand.get("translation", ""),
                case,
                sentence_length=sentence_length,
                run_grammar=run_grammar,
            )
        )
    return scored


# Aggregation ----------------------------------------------------------------


def _rate(scored: list[dict[str, Any]], key: str) -> dict[str, Any]:
    n = len(scored)
    if n == 0:
        return {"n": 0, "correct": 0, "pass_rate": None, "wilson_95_ci": None}
    valid = [s for s in scored if s.get(key) is not None]
    n_valid = len(valid)
    if n_valid == 0:
        return {"n": 0, "correct": 0, "pass_rate": None, "wilson_95_ci": None}
    k = sum(1 for s in valid if s.get(key))
    lo, hi = wilson_ci(k, n_valid)
    return {
        "n": n_valid,
        "correct": k,
        "pass_rate": round(k / n_valid, 4),
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize_run(results: list[dict[str, Any]], *, conditions: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}, "prior_reference": PRIOR_EF_REFERENCE}
    for model_key in {r["model_key"] for r in results}:
        model_rows = [r for r in results if r["model_key"] == model_key]
        out["per_model"][model_key] = {"by_condition": {}}
        for cond in conditions:
            cond_rows = [r for r in model_rows if r["condition"] == cond]
            all_scored: list[dict[str, Any]] = []
            for row in cond_rows:
                all_scored.extend(row["candidates"])
            summary: dict[str, Any] = {
                "expected_form_match": _rate(all_scored, "ef_pass"),
                "length_in_band": _rate(all_scored, "length_in_band"),
                "grammar_languagetool": _rate(all_scored, "grammar_pass"),
                "per_verb": {},
            }
            for row in cond_rows:
                key = row["case"]["keyword"]
                summary["per_verb"][key] = _rate(row["candidates"], "ef_pass")
            out["per_model"][model_key]["by_condition"][cond] = summary
    return out


# Driver ---------------------------------------------------------------------


def run_spike(
    model_keys: list[str],
    *,
    benchmark_names: list[str],
    conditions: list[str],
    samples: int,
    temperature: float,
    sentence_length: str,
    run_grammar: bool,
) -> dict[str, Any]:
    cases = load_benchmark_cases(benchmark_names)
    results: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "models": {k: QWEN_MODELS[k] for k in model_keys},
        "benchmarks": benchmark_names,
        "conditions": conditions,
        "samples_per_case": samples,
        "temperature": temperature,
        "sentence_length": sentence_length,
        "run_grammar": run_grammar,
        "cases": [asdict(c) for c in cases],
        "runs": [],
    }

    for model_key in model_keys:
        model_id = QWEN_MODELS[model_key]
        print(f"\n=== {model_key} ({model_id}) ===")
        for condition in conditions:
            if condition not in CONDITION_BUILDERS:
                raise ValueError(f"Unknown condition: {condition}")
            print(f"  -- {condition} --")
            for i, case in enumerate(cases, 1):
                print(f"    [{i}/{len(cases)}] {case.id}...", flush=True)
                t0 = time.perf_counter()
                scored = run_condition_for_case(
                    model_id,
                    case,
                    condition=condition,
                    samples=samples,
                    temperature=temperature,
                    sentence_length=sentence_length,
                    run_grammar=run_grammar,
                )
                row = {
                    "model_key": model_key,
                    "model_id": model_id,
                    "condition": condition,
                    "case": asdict(case),
                    "latency_s": round(time.perf_counter() - t0, 2),
                    "candidates": [asdict(s) for s in scored],
                }
                results.append(row)
                payload["runs"].append(row)

    payload["summary"] = summarize_run(results, conditions=conditions)
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Spanish form-injection spike (Qwen 0.5B / 1.7B)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(QWEN_MODELS),
        default=["qwen05b", "qwen17b"],
    )
    parser.add_argument("--benchmarks", nargs="+", default=list(_DEFAULT_BENCHMARKS))
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=[
            "baseline",
            "explicit",
            "form_injected",
            "form_injected_explicit",
        ],
    )
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--sentence-length", default="short", dest="sentence_length")
    parser.add_argument(
        "--skip-grammar",
        action="store_true",
        help="Skip LanguageTool scoring (useful when LT is unavailable).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.dry_run:
        cases = load_benchmark_cases(args.benchmarks)
        print(
            f"{len(cases)} cases, conditions={args.conditions}, models={args.models}"
        )
        if cases:
            sample = _build_form_injected(cases[0], n=args.samples, length=args.sentence_length)
            print("--- example form_injected prompt ---")
            print(sample)
        return

    print(
        f"Form-injection spike: benchmarks={args.benchmarks}, conditions={args.conditions}, "
        f"models={args.models}, n={args.samples}, temp={args.temperature}"
    )
    data = run_spike(
        args.models,
        benchmark_names=args.benchmarks,
        conditions=args.conditions,
        samples=args.samples,
        temperature=args.temperature,
        sentence_length=args.sentence_length,
        run_grammar=not args.skip_grammar,
    )

    out_path = args.output or (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "spike-results"
        / "eval_spanish_form_injection_qwen_results.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
