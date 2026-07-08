#!/usr/bin/env python3
"""Build the Direction 1 pilot verb manifest (high + low tier only).

Selects high-tier and low-tier Spanish verbs from the Diagnostic 2 n=150
manifest, balanced across regular/irregular within each tier. Mid-tier verbs
are excluded.

Default: 25 verbs per tier (50 total), split 12 regular + 13 irregular per tier
(seed 42).

Writes:
  research/evaluation/lexicon/experiment_verbs/manifest_direction_hl50.csv

Usage::

    python3 -m research.scripts.build_direction_pilot_manifest
    python3 -m research.scripts.build_direction_pilot_manifest --per-tier 15 \\
        --output research/evaluation/lexicon/experiment_verbs/manifest_direction_hl30.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_2_paradigm_n150.csv"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_direction_hl50.csv"
)
DEFAULT_PER_TIER = 25
EXPERIMENT_ID = "direction_hl50"
TIERS = ("high", "low")


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def select_hl_verbs(
    rows: list[dict[str, str]],
    *,
    per_tier: int = DEFAULT_PER_TIER,
    seed: int = 42,
) -> list[dict[str, str]]:
    """Pick ``per_tier`` verbs from high and low tiers, balanced reg/irreg."""
    if per_tier < 2:
        raise ValueError("per_tier must be at least 2 for reg/irreg balance")

    by_tier_cell: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["lang"] != "es":
            continue
        tier = row["tier"]
        if tier not in TIERS:
            continue
        cell = row["cell_id"]
        by_tier_cell[(tier, cell)].append(row)

    n_reg = per_tier // 2
    n_irreg = per_tier - n_reg
    tier_targets = {
        "high": {"high_regular": n_reg, "high_irregular": n_irreg},
        "low": {"low_regular": n_reg, "low_irregular": n_irreg},
    }

    rng = random.Random(seed)
    picked: list[dict[str, str]] = []
    for tier in TIERS:
        for cell_id, count in tier_targets[tier].items():
            pool = list(by_tier_cell.get((tier, cell_id), []))
            if len(pool) < count:
                raise ValueError(
                    f"Not enough verbs in {cell_id}: need {count}, have {len(pool)}"
                )
            rng.shuffle(pool)
            for row in pool[:count]:
                out = dict(row)
                out["experiment"] = EXPERIMENT_ID
                out["seed"] = str(seed)
                picked.append(out)

    picked.sort(key=lambda r: (r["tier"], r["cell_id"], r["verb"]))
    return picked


def write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    if not rows:
        raise ValueError("No rows to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Direction 1 pilot manifest (high + low tiers only)."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--per-tier",
        type=int,
        default=DEFAULT_PER_TIER,
        help="Verbs per tier (high and low); total = 2 × per_tier (default 50).",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    source_rows = _read_manifest(args.source)
    picked = select_hl_verbs(source_rows, per_tier=args.per_tier, seed=args.seed)
    write_manifest(picked, args.output)

    counts = Counter(r["cell_id"] for r in picked)
    print(f"Wrote {args.output}")
    print(f"  verbs={len(picked)}  seed={args.seed}")
    for cell in sorted(counts):
        print(f"  {cell}: {counts[cell]}")


if __name__ == "__main__":
    main()
