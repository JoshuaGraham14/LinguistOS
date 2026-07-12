#!/usr/bin/env python3
"""Build a frequency × difficulty spike for soft_plain_B beams=8.

2×2 strata from Diagnostic 2's census manifest:
  high Zipf × easy slots | high Zipf × hard slots
  low  Zipf × easy slots | low  Zipf × hard slots

Easy slots ≈ high D2 accuracy (common persons / present-ish).
Hard slots ≈ low D2 accuracy (vosotros + 2sg preterite / conditional).

Usage::

    python -m research.scripts.build_soft_freq_difficulty_spike
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.benchmarks.loader import _validate_raw
from research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike import (
    PARTICIPLE_TENSE,
)
from research.scripts.build_diagnostic_5_benchmark import (
    _resolved_gold_form,
    _resolved_participle,
    lemma_translation,
    write_benchmark_yaml,
)

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "evaluation/lexicon/experiment_verbs/manifest_soft_freq_difficulty_spike.csv"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/spanish_soft_freq_difficulty_spike.yaml"
)

# High-accuracy cells on Qwen3-1.7B Diagnostic 2A/2B.
EASY_SLOTS: list[tuple[str, str, str]] = [
    ("present", "1st", "singular"),
    ("present", "3rd", "singular"),
    ("present", "1st", "plural"),
    ("imperfect", "3rd", "singular"),
    ("future", "1st", "singular"),
]

# Low-accuracy cells: vosotros + rare 2sg past/conditional.
HARD_SLOTS: list[tuple[str, str, str]] = [
    ("present", "2nd", "plural"),
    ("preterite", "2nd", "singular"),
    ("preterite", "2nd", "plural"),
    ("imperfect", "2nd", "plural"),
    ("conditional", "2nd", "plural"),
    ("future", "2nd", "plural"),
]


def load_spike_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_constraint_sets(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    sets: list[dict[str, Any]] = []
    for row in rows:
        lemma = row["verb"]
        translation = lemma_translation(lemma)

        for tense, person, number in EASY_SLOTS:
            sets.append(
                {
                    "keyword": lemma,
                    "translation": translation,
                    "expected_form": _resolved_gold_form(
                        lemma, tense, person, number
                    ),
                    "tense": tense,
                    "person": person,
                    "number": number,
                }
            )
        sets.append(
            {
                "keyword": lemma,
                "translation": translation,
                "expected_form": _resolved_participle(row),
                "tense": PARTICIPLE_TENSE,
            }
        )
        for tense, person, number in HARD_SLOTS:
            sets.append(
                {
                    "keyword": lemma,
                    "translation": translation,
                    "expected_form": _resolved_gold_form(
                        lemma, tense, person, number
                    ),
                    "tense": tense,
                    "person": person,
                    "number": number,
                }
            )
    return sets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--name", default="spanish_soft_freq_difficulty_spike")
    args = parser.parse_args()

    rows = load_spike_manifest(args.manifest)
    high = [r for r in rows if r["tier"] == "high"]
    low = [r for r in rows if r["tier"] == "low"]
    if not high or not low:
        raise SystemExit(f"Manifest must contain high and low tiers: {args.manifest}")

    payload = {
        "name": args.name,
        "language": "es",
        "description": (
            "Spike: soft_plain_B beams=8 on Diagnostic-2 Zipf extremes × "
            "easy vs hard morphological slots. High verbs: "
            + ", ".join(r["verb"] for r in high)
            + ". Low verbs: "
            + ", ".join(r["verb"] for r in low)
            + "."
        ),
        "constraint_sets": build_constraint_sets(rows),
    }
    write_benchmark_yaml(payload, args.output)
    n = len(payload["constraint_sets"])
    print(f"Wrote {args.output}")
    print(f"  verbs={len(rows)} (high={len(high)} low={len(low)})  cells={n}")
    print(f"  strata: high×easy, high×hard, low×easy, low×hard")

    with args.output.open(encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    _validate_raw(loaded, args.output)
    print("  validation: ok")


if __name__ == "__main__":
    main()
