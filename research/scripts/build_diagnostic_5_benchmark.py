#!/usr/bin/env python3
"""Build the Diagnostic 5 pipeline benchmark YAML from the n=150 census manifest.

Writes ``research/benchmarks/spanish_diagnostic_n150.yaml`` with 150 verbs × 31
cells (5 indicative tenses × 6 persons + past participle) = 4,650 constraint
sets. Gold forms come from verbecc (same helpers as Diagnostic 2).

Usage::

    python -m research.scripts.build_diagnostic_5_benchmark
    python -m research.scripts.build_diagnostic_5_benchmark --limit-verbs 2 \\
        --output research/benchmarks/spanish_diagnostic_n150_smoke.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.benchmarks.loader import _validate_raw
from research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike import (
    DEFAULT_MANIFEST,
    INDICATIVE_TENSES,
    PARTICIPLE_TENSE,
    PERSON_NUMBER_SLOTS,
    gold_form,
    gold_participle,
    load_manifest,
)

BENCHMARK_NAME = "spanish_diagnostic_n150"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "benchmarks" / f"{BENCHMARK_NAME}.yaml"
)


def lemma_translation(lemma: str) -> str:
    """Manifest rows have no English gloss; keep lemma as placeholder (Diag 3/4)."""
    return lemma


def build_constraint_sets(
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    sets: list[dict[str, Any]] = []
    for row in manifest_rows:
        lemma = row["verb"]
        translation = lemma_translation(lemma)
        for tense in INDICATIVE_TENSES:
            for person, number, _label in PERSON_NUMBER_SLOTS:
                sets.append(
                    {
                        "keyword": lemma,
                        "translation": translation,
                        "expected_form": gold_form(lemma, tense, person, number),
                        "tense": tense,
                        "person": person,
                        "number": number,
                    }
                )
        sets.append(
            {
                "keyword": lemma,
                "translation": translation,
                "expected_form": gold_participle(row),
                "tense": PARTICIPLE_TENSE,
            }
        )
    return sets


def build_benchmark_payload(
    manifest_rows: list[dict[str, str]],
    *,
    name: str = BENCHMARK_NAME,
) -> dict[str, Any]:
    constraint_sets = build_constraint_sets(manifest_rows)
    return {
        "name": name,
        "language": "es",
        "description": (
            "Diagnostic 5 sentence grid: census-validated Spanish verbs from "
            "manifest_diagnostic_2_paradigm_n150.csv. Each verb has five "
            "indicative tenses × six persons plus past participle (31 cells). "
            "Paired pipeline runs: baseline (5A), form-injected (5B), "
            "form-injected + explicit overlay (5C). No CEFR band (production "
            "diagnostic ladder). Gold forms from verbecc / manifest participles."
        ),
        "constraint_sets": constraint_sets,
    }


def write_benchmark_yaml(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep a stable, readable dump; block style for long description.
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            payload,
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=88,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Diagnostic 5 spanish_diagnostic_n150 benchmark YAML."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Spanish verb manifest CSV (default: Diagnostic 2 n=150).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output YAML path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--name",
        default=BENCHMARK_NAME,
        help="Benchmark name field (must match filename for run_experiment).",
    )
    parser.add_argument(
        "--limit-verbs",
        type=int,
        default=None,
        help="Only first N verbs (smoke subsets).",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip loader validation after write.",
    )
    args = parser.parse_args()

    rows = load_manifest(args.manifest)
    if args.limit_verbs is not None:
        rows = rows[: args.limit_verbs]

    payload = build_benchmark_payload(rows, name=args.name)
    n_sets = len(payload["constraint_sets"])
    expected = len(rows) * 31
    if n_sets != expected:
        raise RuntimeError(f"Expected {expected} constraint sets, built {n_sets}")

    write_benchmark_yaml(payload, args.output)
    print(f"Wrote {args.output}")
    print(f"  verbs={len(rows)}  constraint_sets={n_sets}  name={args.name}")

    if not args.skip_validate:
        with args.output.open(encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        _validate_raw(loaded, args.output)
        print("  validation: ok")


if __name__ == "__main__":
    main()
