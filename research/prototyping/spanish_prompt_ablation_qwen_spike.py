#!/usr/bin/env python3
"""Spanish prompt ablation spike — Qwen 0.5B / 1.7B (prototyping; not the pipeline).

Compares sentence-generation EF pass rates under:
  - baseline: current ``build_prompt`` (matches baseline_hf)
  - explicit: ``build_prompt_explicit`` (stronger morphology instructions)
  - self_correct: baseline pass@1 then one constraint-guided rewrite per EF failure (no gold form in fix prompt)

Benchmarks: spanish_basic, spanish_challenging, spanish_niche.

Results: docs/spike-results/eval_spanish_prompt_ablation_qwen_results.json
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
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    parse_candidates_lenient,
)
from research.generation.languages import extract_constraints, load_language_profile
from research.generation.prompt_builder import (
    build_prompt,
    build_prompt_explicit,
    language_display_name,
)

_BENCHMARKS_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
_DEFAULT_BENCHMARKS = ("spanish_basic", "spanish_challenging", "spanish_niche")

QWEN_MODELS: dict[str, str] = {
    "qwen05b": "Qwen/Qwen2.5-0.5B-Instruct",
    "qwen17b": "Qwen/Qwen3-1.7B",
}

PRIOR_EF_REFERENCE: dict[str, float] = {
    "qwen05b_spanish_basic": 0.06,
    "qwen17b_spanish_basic": 0.21,
}

_EF = ExpectedFormMatchEvaluator()


@dataclass
class BenchmarkCase:
    id: str
    benchmark: str
    tier: str
    keyword: str
    translation: str
    constraints: dict[str, Any]
    cefr_level: str | None = None


@dataclass
class ScoredCandidate:
    sentence: str
    translation: str
    ef_pass: bool
    expected_form: str | None
    corrected: bool = False
    pass_at_2: bool | None = None
    corrected_sentence: str | None = None
    corrected_translation: str | None = None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p_hat = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _tier_for_benchmark(name: str) -> str:
    return {
        "spanish_basic": "common_regular",
        "spanish_challenging": "common_irregular",
        "spanish_niche": "rare",
    }.get(name, "unknown")


def load_benchmark_cases(benchmark_names: list[str]) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for bm_name in benchmark_names:
        path = _BENCHMARKS_DIR / f"{bm_name}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        tier = _tier_for_benchmark(bm_name)
        for i, cs in enumerate(data["constraint_sets"]):
            constraints = extract_constraints(cs)
            if cs.get("expected_form"):
                constraints["expected_form"] = cs["expected_form"]
            tense = cs.get("tense", "")
            person = cs.get("person", "")
            number = cs.get("number", "")
            case_id = f"{bm_name}__{cs['keyword']}__{tense}_{person}_{number}__{i}"
            cases.append(
                BenchmarkCase(
                    id=case_id,
                    benchmark=bm_name,
                    tier=tier,
                    keyword=cs["keyword"],
                    translation=cs["translation"],
                    constraints=constraints,
                    cefr_level=cs.get("cefr_level"),
                )
            )
    return cases


def ef_pass(sentence: str, translation: str, constraints: dict[str, Any]) -> bool:
    result = _EF.evaluate(sentence, translation, constraints)
    return bool(result.details.get("passed"))


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


def parse_single_candidate(raw: str) -> dict[str, str] | None:
    """Parse one sentence/translation pair from a correction response."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("sentence"):
            return {
                "sentence": str(data["sentence"]).strip(),
                "translation": str(data.get("translation", "")).strip(),
            }
    except json.JSONDecodeError:
        pass
    cands, _ = parse_candidates_lenient(raw)
    return cands[0] if cands else None


def hf_generate_single(
    model_id: str,
    prompt: str,
    *,
    temperature: float = 0.7,
    target_language: str = "es",
) -> dict[str, str] | None:
    gen = BaselineHFGenerator(model=model_id, temperature=temperature)
    raw = gen._call(prompt, _system_message(target_language), max_new_tokens=256)
    return parse_single_candidate(raw)


def _constraint_summary(constraints: dict[str, Any]) -> str:
    profile = load_language_profile("es")
    parts: list[str] = []
    for field in profile.dimension_fields():
        if field not in constraints:
            continue
        label = profile.label_for(field)
        display = profile.gloss_for(field, str(constraints[field]))
        parts.append(f"{label}: {display}")
    return "; ".join(parts) if parts else "see original task constraints"


def build_correction_prompt(case: BenchmarkCase, scored: ScoredCandidate) -> str:
    summary = _constraint_summary(case.constraints)
    return (
        f'The Spanish sentence below may not correctly conjugate the verb '
        f'"{case.keyword}" (English: "{case.translation}").\n'
        f"Required morphology: {summary}.\n"
        f'Do not leave the verb as the infinitive "{case.keyword}".\n'
        "Review the sentence and rewrite it so the verb form matches the constraints.\n"
        'Reply ONLY as JSON: {"sentence":"...","translation":"..."}\n\n'
        f"Original sentence: {scored.sentence}\n"
        f"Original translation: {scored.translation}"
    )


def build_explicit_prompt(
    case: BenchmarkCase,
    *,
    num_candidates: int,
    sentence_length: str = "short",
) -> str:
    return build_prompt_explicit(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=case.cefr_level,
    )


def build_baseline_prompt(
    case: BenchmarkCase,
    *,
    num_candidates: int,
    sentence_length: str = "short",
) -> str:
    return build_prompt(
        keyword=case.keyword,
        translation=case.translation,
        target_language="es",
        constraints=case.constraints,
        num_candidates=num_candidates,
        sentence_length=sentence_length,
        cefr_level=case.cefr_level,
    )


PromptBuilder = Callable[..., str]


def run_baseline_condition(
    model_id: str,
    case: BenchmarkCase,
    *,
    samples: int,
    temperature: float,
    sentence_length: str,
    prompt_builder: PromptBuilder,
) -> list[ScoredCandidate]:
    prompt = prompt_builder(
        case,
        num_candidates=samples,
        sentence_length=sentence_length,
    )
    raw_cands = hf_generate_batched(
        model_id,
        prompt,
        samples,
        temperature=temperature,
    )
    scored: list[ScoredCandidate] = []
    for cand in raw_cands:
        passed = ef_pass(cand["sentence"], cand["translation"], case.constraints)
        scored.append(
            ScoredCandidate(
                sentence=cand["sentence"],
                translation=cand["translation"],
                ef_pass=passed,
                expected_form=case.constraints.get("expected_form"),
            )
        )
    return scored


def run_self_correct_condition(
    model_id: str,
    case: BenchmarkCase,
    *,
    samples: int,
    temperature: float,
    sentence_length: str,
) -> list[ScoredCandidate]:
    scored = run_baseline_condition(
        model_id,
        case,
        samples=samples,
        temperature=temperature,
        sentence_length=sentence_length,
        prompt_builder=build_baseline_prompt,
    )
    for item in scored:
        item.pass_at_2 = item.ef_pass
        if item.ef_pass:
            continue
        expected = case.constraints.get("expected_form")
        if not expected:
            continue
        correction_prompt = build_correction_prompt(case, item)
        fixed = hf_generate_single(model_id, correction_prompt, temperature=temperature)
        if not fixed or not fixed.get("sentence"):
            continue
        item.corrected = True
        item.corrected_sentence = fixed["sentence"]
        item.corrected_translation = fixed.get("translation") or item.translation
        if ef_pass(item.corrected_sentence, item.corrected_translation, case.constraints):
            item.pass_at_2 = True
    return scored


def _candidate_pass(scored: ScoredCandidate | dict[str, Any], *, use_pass_at_2: bool) -> bool:
    if isinstance(scored, dict):
        if use_pass_at_2:
            return bool(scored.get("pass_at_2"))
        return bool(scored.get("ef_pass"))
    if use_pass_at_2:
        return bool(scored.pass_at_2)
    return scored.ef_pass


def _rate(scored: list[ScoredCandidate | dict[str, Any]], *, use_pass_at_2: bool = False) -> dict[str, Any]:
    n = len(scored)
    if n == 0:
        return {"n": 0, "correct": 0, "pass_rate": None, "wilson_95_ci": None}
    k = sum(1 for s in scored if _candidate_pass(s, use_pass_at_2=use_pass_at_2))
    lo, hi = wilson_ci(k, n)
    return {
        "n": n,
        "correct": k,
        "pass_rate": round(k / n, 4),
        "wilson_95_ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
    }


def summarize_run(
    results: list[dict[str, Any]],
    *,
    conditions: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {"per_model": {}, "prior_reference": PRIOR_EF_REFERENCE}
    for model_key in {r["model_key"] for r in results}:
        model_rows = [r for r in results if r["model_key"] == model_key]
        out["per_model"][model_key] = {"by_condition": {}}
        for cond in conditions:
            cond_rows = [r for r in model_rows if r["condition"] == cond]
            all_scored: list[dict[str, Any]] = []
            for row in cond_rows:
                all_scored.extend(row["candidates"])
            use_p2 = cond == "self_correct"
            summary: dict[str, Any] = {
                "overall": _rate(all_scored, use_pass_at_2=use_p2),
                "pass_at_1": _rate(all_scored, use_pass_at_2=False) if use_p2 else None,
                "by_benchmark": {},
            }
            if use_p2:
                attempts = sum(1 for s in all_scored if not s.get("ef_pass"))
                fixed = sum(
                    1 for s in all_scored if s.get("corrected") and s.get("pass_at_2")
                )
                summary["correction"] = {
                    "failures_at_1": attempts,
                    "correction_attempts": attempts,
                    "corrections_successful": fixed,
                    "correction_yield": round(fixed / attempts, 4) if attempts else None,
                }
            for bm in _DEFAULT_BENCHMARKS:
                bm_scored: list[dict[str, Any]] = []
                for row in cond_rows:
                    if row["case"]["benchmark"] == bm:
                        bm_scored.extend(row["candidates"])
                summary["by_benchmark"][bm] = _rate(bm_scored, use_pass_at_2=use_p2)
            out["per_model"][model_key]["by_condition"][cond] = summary
    return out


VALID_CONDITIONS = frozenset({"baseline", "explicit", "self_correct"})


def run_ablation(
    model_keys: list[str],
    *,
    benchmark_names: list[str],
    conditions: list[str],
    samples: int,
    temperature: float,
    sentence_length: str,
    prompt_builders: dict[str, PromptBuilder],
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
        "cases": [asdict(c) for c in cases],
        "runs": [],
    }

    for model_key in model_keys:
        model_id = QWEN_MODELS[model_key]
        print(f"\n=== {model_key} ({model_id}) ===")
        for condition in conditions:
            if condition not in VALID_CONDITIONS:
                raise ValueError(f"Unknown condition: {condition}")
            print(f"  -- {condition} --")
            for i, case in enumerate(cases, 1):
                print(f"    [{i}/{len(cases)}] {case.id}...", flush=True)
                t0 = time.perf_counter()
                if condition == "self_correct":
                    scored = run_self_correct_condition(
                        model_id,
                        case,
                        samples=samples,
                        temperature=temperature,
                        sentence_length=sentence_length,
                    )
                else:
                    builder = prompt_builders[condition]
                    scored = run_baseline_condition(
                        model_id,
                        case,
                        samples=samples,
                        temperature=temperature,
                        sentence_length=sentence_length,
                        prompt_builder=builder,
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

    parser = argparse.ArgumentParser(description="Spanish prompt ablation (Qwen 0.5B / 1.7B)")
    parser.add_argument("--models", nargs="+", choices=list(QWEN_MODELS), default=["qwen05b", "qwen17b"])
    parser.add_argument("--benchmarks", nargs="+", default=list(_DEFAULT_BENCHMARKS))
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["baseline", "explicit", "self_correct"],
    )
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--sentence-length", default="short", dest="sentence_length")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    builders: dict[str, PromptBuilder] = {
        "baseline": build_baseline_prompt,
        "explicit": build_explicit_prompt,
    }

    if args.dry_run:
        cases = load_benchmark_cases(args.benchmarks)
        print(f"{len(cases)} cases, conditions={args.conditions}, models={args.models}")
        if cases:
            sample = build_baseline_prompt(cases[0], num_candidates=args.samples)
            print(sample[:500])
        return

    print(
        f"Prompt ablation: benchmarks={args.benchmarks}, conditions={args.conditions}, "
        f"models={args.models}, n={args.samples}, temp={args.temperature}"
    )
    data = run_ablation(
        args.models,
        benchmark_names=args.benchmarks,
        conditions=args.conditions,
        samples=args.samples,
        temperature=args.temperature,
        sentence_length=args.sentence_length,
        prompt_builders=builders,
    )

    out_path = args.output or (
        Path(__file__).resolve().parents[2] / "docs" / "spike-results" / "eval_spanish_prompt_ablation_qwen_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n--- Summary ---")
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
