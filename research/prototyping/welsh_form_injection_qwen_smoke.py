#!/usr/bin/env python3
"""Welsh transfer smoke: vanilla vs form-inject on a few syn + peri cells.

Loads ``research/benchmarks/welsh_smoke.yaml``, generates with Qwen (default
0.6B), and scores with the mutation/aux-aware expected-form matcher.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.generation.baseline_hf import BaselineHFGenerator, FormInjectedHFGenerator
from research.generation.languages import extract_constraints
from research.generation.prompt_builder import build_prompt

_ROOT = Path(__file__).resolve().parents[1]
_BENCHMARKS = _ROOT / "benchmarks"
_DEFAULT_OUT = _ROOT / "welsh" / "manifests" / "welsh_smoke_results.json"

MODELS = {
    "qwen06b": "Qwen/Qwen3-0.6B",
    "qwen17b": "Qwen/Qwen3-1.7B",
}

_EF = ExpectedFormMatchEvaluator()


@dataclass
class SmokeCase:
    id: str
    keyword: str
    translation: str
    expected_form: str
    constraints: dict[str, Any]
    cell_id: str
    construction: str


def load_cases(name: str) -> list[SmokeCase]:
    path = _BENCHMARKS / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[SmokeCase] = []
    for i, cs in enumerate(data["constraint_sets"]):
        constraints = extract_constraints(cs)
        for key in (
            "expected_form",
            "expected_form_alts",
            "expected_aux",
            "expected_aux_alts",
            "particle",
        ):
            if cs.get(key):
                constraints[key] = cs[key]
        cell_id = cs.get("cell_id", f"idx{i}")
        out.append(
            SmokeCase(
                id=f"{cs['keyword']}__{cell_id}",
                keyword=cs["keyword"],
                translation=cs["translation"],
                expected_form=cs["expected_form"],
                constraints=constraints,
                cell_id=cell_id,
                construction=cs["construction"],
            )
        )
    return out


def score_sentence(sentence: str, case: SmokeCase) -> dict[str, Any]:
    result = _EF.evaluate(sentence, "", case.constraints)
    return {
        "sentence": sentence,
        "ef_pass": bool(result.details.get("passed")),
        "ef_details": result.details,
    }


def run_condition(
    *,
    label: str,
    generator: BaselineHFGenerator,
    cases: list[SmokeCase],
    samples: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        t0 = time.time()
        cands = generator.generate(
            keyword=case.keyword,
            translation=case.translation,
            constraints=case.constraints,
            num_candidates=samples,
            target_language="cy",
            cefr_level="A2",
            sentence_length="short",
        )
        elapsed = time.time() - t0
        scored = [score_sentence(c.get("sentence", ""), case) for c in cands]
        n_pass = sum(1 for s in scored if s["ef_pass"])
        rows.append(
            {
                "condition": label,
                "case_id": case.id,
                "cell_id": case.cell_id,
                "construction": case.construction,
                "keyword": case.keyword,
                "expected_form": case.expected_form,
                "expected_aux": case.constraints.get("expected_aux"),
                "n": len(scored),
                "ef_pass_n": n_pass,
                "ef_rate": (n_pass / len(scored)) if scored else None,
                "elapsed_s": round(elapsed, 2),
                "candidates": scored,
            }
        )
        print(
            f"  [{label}] {case.cell_id:28} {case.keyword:8} "
            f"EF {n_pass}/{len(scored)}  ({elapsed:.1f}s)"
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", default="welsh_smoke")
    ap.add_argument("--model", choices=sorted(MODELS), default="qwen17b")
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--conditions", nargs="+", default=["vanilla", "inject"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = ap.parse_args()

    cases = load_cases(args.benchmark)
    print(f"Loaded {len(cases)} cases from {args.benchmark}")
    syn = sum(1 for c in cases if c.construction == "synthetic")
    peri = sum(1 for c in cases if c.construction == "periphrastic")
    print(f"  synthetic={syn} periphrastic={peri}")

    if args.dry_run:
        for case in cases:
            for cond in args.conditions:
                inject = case.expected_form if cond == "inject" else None
                prompt = build_prompt(
                    keyword=case.keyword,
                    translation=case.translation,
                    target_language="cy",
                    constraints=case.constraints,
                    num_candidates=args.samples,
                    sentence_length="short",
                    cefr_level="A2",
                    inject_expected_form=inject,
                )
                print(f"\n===== {cond} / {case.id} =====\n{prompt}")
        return

    model_id = MODELS[args.model]
    print(f"Model: {model_id}")
    gens: dict[str, BaselineHFGenerator] = {}
    if "vanilla" in args.conditions:
        gens["vanilla"] = BaselineHFGenerator(model=model_id, temperature=0.7)
    if "inject" in args.conditions:
        gens["inject"] = FormInjectedHFGenerator(model=model_id, temperature=0.7)

    all_rows: list[dict[str, Any]] = []
    for label, gen in gens.items():
        print(f"\n=== {label} ===")
        all_rows.extend(
            run_condition(label=label, generator=gen, cases=cases, samples=args.samples)
        )

    summary: dict[str, Any] = {"by_condition": {}, "by_construction": {}}
    for label in gens:
        sub = [r for r in all_rows if r["condition"] == label]
        n = sum(r["n"] for r in sub)
        k = sum(r["ef_pass_n"] for r in sub)
        summary["by_condition"][label] = {"ef_pass_n": k, "n": n, "ef_rate": k / n if n else None}
        for cons in ("synthetic", "periphrastic"):
            subc = [r for r in sub if r["construction"] == cons]
            nc = sum(r["n"] for r in subc)
            kc = sum(r["ef_pass_n"] for r in subc)
            summary["by_construction"].setdefault(label, {})[cons] = {
                "ef_pass_n": kc,
                "n": nc,
                "ef_rate": kc / nc if nc else None,
            }

    payload = {
        "benchmark": args.benchmark,
        "model": model_id,
        "samples": args.samples,
        "summary": summary,
        "rows": all_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {args.out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
