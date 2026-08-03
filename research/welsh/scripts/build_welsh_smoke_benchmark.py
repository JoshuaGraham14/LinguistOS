"""Build a tiny Welsh smoke benchmark YAML from the gold case table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "research" / "welsh" / "manifests" / "welsh_cases_n150.csv"
OUT = ROOT / "research" / "benchmarks" / "welsh_smoke.yaml"

# Few cells covering synthetic + periphrastic across tenses.
SMOKE_CELLS: tuple[tuple[str, str], ...] = (
    ("rhoi", "synthetic_present_1s"),
    ("rhoi", "synthetic_past_3s"),
    ("rhoi", "periphrastic_present_1s"),
    ("rhoi", "periphrastic_past_1s"),
    ("credu", "synthetic_imperfect_2s"),
    ("credu", "periphrastic_future_3s"),
    ("credu", "periphrastic_imperfect_1p"),
    ("troi", "synthetic_present_3s"),
    ("troi", "periphrastic_past_2s"),
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    cases = pd.read_csv(args.cases, keep_default_na=False)
    rows: list[dict] = []
    for lemma, cell_id in SMOKE_CELLS:
        hit = cases[(cases["lemma"] == lemma) & (cases["cell_id"] == cell_id)]
        if hit.empty:
            raise SystemExit(f"Missing case {lemma} / {cell_id}")
        r = hit.iloc[0]
        item = {
            "keyword": lemma,
            "translation": str(r["enlemma"]).replace("_", " "),
            "expected_form": r["gold"],
            "tense": r["tense"],
            "person": r["probed_person"],
            "number": r["probed_number"],
            "construction": r["construction"],
            "cell_id": cell_id,
            "cefr_level": "A2",
        }
        if r["gold_alts"]:
            item["expected_form_alts"] = r["gold_alts"]
        if r["construction"] == "periphrastic":
            item["expected_aux"] = r["aux_gold"]
            if r["aux_gold_alts"]:
                item["expected_aux_alts"] = r["aux_gold_alts"]
            if r["particle"]:
                item["particle"] = r["particle"]
        rows.append(item)

    doc = {
        "name": "welsh_smoke",
        "language": "cy",
        "description": (
            "Tiny Welsh transfer smoke set: synthetic + periphrastic cells "
            "drawn from welsh_cases_n150.csv (Eurfa gold)."
        ),
        "constraint_sets": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {args.out} ({len(rows)} cases)")


if __name__ == "__main__":
    main()
