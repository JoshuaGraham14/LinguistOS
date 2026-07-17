#!/usr/bin/env python3
"""Audit known lexical ambiguity in Direction 3 morphology ban sets."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import yaml

from research.generation.morph_bans import build_morph_ban_set

DEFAULT_BENCHMARK = Path(
    "research/benchmarks/spanish_direction_hl50_smoke5.yaml"
)

# These forms are valid conjugations in smoke5 but also common words/usages.
KNOWN_AMBIGUOUS: dict[str, str] = {
    "busca": "also a noun / lexicalised expression ('search')",
    "cerca": "also the adverb/preposition 'near'",
    "cerco": "also the noun 'siege/enclosure'",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report ambiguous surface forms banned by Direction 3"
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    args = parser.parse_args()

    raw = yaml.safe_load(args.benchmark.read_text(encoding="utf-8"))
    cells = raw["constraint_sets"]
    surface_counts: Counter[str] = Counter()
    ambiguous_cells: list[tuple[int, str, str, tuple[str, ...]]] = []

    for index, cell in enumerate(cells, start=1):
        ban_set = build_morph_ban_set(
            cell["keyword"],
            cell["tense"],
            cell.get("person", ""),
            cell.get("number", ""),
            cell["expected_form"],
        )
        surface_counts.update(ban_set.surfaces)
        ambiguous = tuple(sorted(ban_set.surfaces & KNOWN_AMBIGUOUS.keys()))
        if ambiguous:
            ambiguous_cells.append(
                (index, cell["keyword"], cell["expected_form"], ambiguous)
            )

    print(
        f"Benchmark: {raw['name']} — {len(cells)} cells, "
        f"{len(surface_counts)} distinct banned surfaces"
    )
    print("\nKnown ambiguous banned forms:")
    for surface in sorted(KNOWN_AMBIGUOUS):
        print(
            f"  {surface:<8} cells={surface_counts[surface]:>3}  "
            f"{KNOWN_AMBIGUOUS[surface]}"
        )
    print(f"\nCells affected by known ambiguity: {len(ambiguous_cells)}")
    for index, lemma, expected, ambiguous in ambiguous_cells:
        print(
            f"  cell={index:>3} lemma={lemma:<11} expected={expected:<14} "
            f"bans={','.join(ambiguous)}"
        )
    print(
        "\nPolicy: report these collisions; do not auto-whitelist them. "
        "This experiment prioritises target-verb morphology in short drills."
    )


if __name__ == "__main__":
    main()
