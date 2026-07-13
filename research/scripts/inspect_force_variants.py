#!/usr/bin/env python3
"""Print `encode_force_variants` for every ``expected_form`` in a benchmark.

Debug helper for Direction 1.2: verify that gold surface forms tokenise cleanly
(single BPE token, or short consistent multi-token sequence) with a given HF
model. Flags forms whose tokens don't round-trip to the surface string —
sign of accent/casing mismatches that would silently break `force_words_ids`.

Usage::

    python3 -m research.scripts.inspect_force_variants \\
        --benchmark research/benchmarks/spanish_direction_hl50.yaml \\
        --model Qwen/Qwen3-1.7B

    # short summary only (token count histogram)
    python3 -m research.scripts.inspect_force_variants \\
        --benchmark research/benchmarks/spanish_direction_hl50.yaml \\
        --summary
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import yaml


def _load_expected_forms(path: Path) -> list[dict[str, str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for cs in data.get("constraint_sets", []):
        form = str(cs.get("expected_form") or "").strip()
        if not form:
            continue
        rows.append(
            {
                "keyword": str(cs.get("keyword", "")),
                "tense": str(cs.get("tense", "")),
                "person": str(cs.get("person", "")),
                "number": str(cs.get("number", "")),
                "expected_form": form,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect force_words_ids token variants for a benchmark's expected_forms",
    )
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print token-length histogram + suspicious cases",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only inspect first N cells (default: all)",
    )
    args = parser.parse_args()

    rows = _load_expected_forms(args.benchmark)
    if args.limit:
        rows = rows[: args.limit]

    from transformers import AutoTokenizer

    from research.generation.constrained_hf import encode_force_variants

    tok = AutoTokenizer.from_pretrained(args.model)

    hist: Counter[int] = Counter()
    suspicious: list[tuple[dict[str, str], list[list[int]]]] = []

    for row in rows:
        variants = encode_force_variants(tok, row["expected_form"])
        for v in variants:
            hist[len(v)] += 1
        # A variant is "suspicious" if decode round-trip drops accents/case
        # or splits into >3 pieces (common when accents force byte-level BPE).
        clean_form = row["expected_form"]
        for v in variants:
            decoded = tok.decode(v).strip()
            drift = decoded.lower() != clean_form.lower() and decoded.strip().lower() != clean_form.lower()
            long_split = len(v) > 3
            if drift or long_split:
                suspicious.append((row, variants))
                break

        if not args.summary:
            pieces_str = " | ".join(
                " ".join(tok.decode([t]) for t in v) for v in variants
            )
            print(
                f"  {row['keyword']:16} {row['tense']:12} {row['person']}/{row['number']:8} "
                f'"{row["expected_form"]}"  variants={variants}  '
                f"pieces=[{pieces_str}]"
            )

    print("\n=== token-length histogram (variants) ===")
    for length in sorted(hist):
        print(f"  {length} token(s): {hist[length]}")

    if suspicious:
        print(f"\n=== suspicious tokenisations ({len(suspicious)}) ===")
        for row, variants in suspicious[:50]:
            decoded_all = [tok.decode(v) for v in variants]
            print(
                f"  {row['keyword']:16} {row['tense']:12} {row['person']}/{row['number']:8} "
                f'form="{row["expected_form"]}"  '
                f"decoded_variants={decoded_all}"
            )
        if len(suspicious) > 50:
            print(f"  ...and {len(suspicious) - 50} more")
    else:
        print("\nNo suspicious tokenisations detected.")


if __name__ == "__main__":
    main()
