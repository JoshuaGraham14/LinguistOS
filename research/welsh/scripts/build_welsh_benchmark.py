"""Build the full Welsh transfer benchmark YAML from the gold case table.

Expands ``welsh_cases_n150.csv`` (150 verbs × 42 cells = 6300) into
``research/benchmarks/welsh_transfer_n150.yaml`` for ``run_experiment``.

Usage::

    python -m research.welsh.scripts.build_welsh_benchmark
    python -m research.welsh.scripts.build_welsh_benchmark --limit-verbs 2 \\
        --out research/benchmarks/welsh_transfer_n150_smoke.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from research.benchmarks.loader import _validate_raw

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "research" / "welsh" / "manifests" / "welsh_cases_n150.csv"
OUT = ROOT / "research" / "benchmarks" / "welsh_transfer_n150.yaml"

BENCHMARK_NAME = "welsh_transfer_n150"


def case_to_constraint_set(r: pd.Series) -> dict:
    item: dict = {
        "keyword": r["lemma"],
        "translation": str(r["enlemma"]).replace("_", " "),
        "expected_form": r["gold"],
        "tense": r["tense"],
        "person": r["probed_person"],
        "number": r["probed_number"],
        "construction": r["construction"],
        "cell_id": r["cell_id"],
        "cefr_level": "A2",
    }
    if r.get("gold_alts"):
        item["expected_form_alts"] = r["gold_alts"]
    if r["construction"] == "periphrastic":
        item["expected_aux"] = r["aux_gold"]
        if r.get("aux_gold_alts"):
            item["expected_aux_alts"] = r["aux_gold_alts"]
        if r.get("particle"):
            item["particle"] = r["particle"]
    # Analysis metadata (scaffold — not validated as dimensions).
    if "tier" in r and r["tier"] != "":
        item["tier"] = r["tier"]
    if "zipf" in r and r["zipf"] != "":
        item["zipf"] = float(r["zipf"])
    return item


def build_rows(cases: pd.DataFrame) -> list[dict]:
    # Stable order: tier → lemma → construction → tense → person code in cell_id.
    ordered = cases.sort_values(
        ["tier", "freq_rank", "lemma", "construction", "tense", "person"],
        kind="mergesort",
    )
    return [case_to_constraint_set(r) for _, r in ordered.iterrows()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--name", default=BENCHMARK_NAME)
    ap.add_argument(
        "--limit-verbs",
        type=int,
        default=0,
        help="If >0, keep only the first N unique lemmas (after sort) for smoke subsets.",
    )
    ap.add_argument("--skip-validate", action="store_true")
    args = ap.parse_args()

    cases = pd.read_csv(args.cases, keep_default_na=False)
    if args.limit_verbs and args.limit_verbs > 0:
        lemmas = (
            cases.sort_values(["tier", "freq_rank", "lemma"], kind="mergesort")["lemma"]
            .drop_duplicates()
            .head(args.limit_verbs)
            .tolist()
        )
        cases = cases[cases["lemma"].isin(lemmas)].copy()

    rows = build_rows(cases)
    n_verbs = cases["lemma"].nunique()
    doc = {
        "name": args.name if not args.limit_verbs else f"{args.name}_v{args.limit_verbs}",
        "language": "cy",
        "description": (
            f"Welsh transfer benchmark: {n_verbs} verbs × 42 cells "
            f"(3×6 synthetic + 4×6 periphrastic) = {len(rows)} constraint sets. "
            "Gold from Eurfa via welsh_cases_n150.csv; soft mutation rule-derived "
            "for periphrastic past."
        ),
        "constraint_sets": rows,
    }

    if not args.skip_validate:
        _validate_raw(doc, path=args.out)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(
        f"Wrote {args.out} ({len(rows)} cases, {n_verbs} verbs, "
        f"{len(rows) // max(n_verbs, 1)} cells/verb)"
    )


if __name__ == "__main__":
    main()
