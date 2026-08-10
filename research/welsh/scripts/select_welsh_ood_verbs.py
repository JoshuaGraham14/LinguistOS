#!/usr/bin/env python3
"""Select Welsh LoRA OOD verbs: 12 per Zipf tier (36 total), exclude n150.

Mirrors ``research.scripts.select_lora_ood_verbs`` for Spanish, but uses the
frozen Welsh coverage pool (Eurfa ∩ CorCenCC terciles) so OOD tiers match the
n150 train set.

Hard requirements for every selected lemma:
  - disjoint from ``manifest_welsh_n150.csv`` (and optional extra excludes)
  - Eurfa coverage already certified in the pool: verbnoun + synthetic
    present/past/imperfect × 6 persons (unlocks the full 42-cell grid;
    periphrastic cells use aux paradigms of *bod*/*gwneud* + verbnoun)
  - not in the Welsh QA blocklist / auxiliaries

Usage::

    python -m research.welsh.scripts.select_welsh_ood_verbs
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import pandas as pd

from research.welsh.scripts.select_welsh_verbs import (
    BLOCKLIST,
    EXCLUDED_AUX,
    MANIFEST_DIR,
    TIERS,
    sample_tiers,
)

EXPERIMENT_ID = "welsh_transfer_ood"
DEFAULT_POOL = MANIFEST_DIR / "welsh_coverage_pool.csv"
DEFAULT_EXCLUDE = MANIFEST_DIR / "manifest_welsh_n150.csv"
DEFAULT_OUT = MANIFEST_DIR / "manifest_welsh_ood_n36.csv"
DEFAULT_SUMMARY = MANIFEST_DIR / "manifest_welsh_ood_n36_summary.json"

# Extra lemmas to keep out of OOD even if they pass coverage: few-shot pool
# exemplars (so prompt demos stay disjoint) and a few awkward / loan-like
# leftovers that slipped past the main blocklist.
FEWSHOT_EXEMPLAR_LEMMAS = frozenset(
    {
        "canu",
        "gweld",
        "siarad",
        "helpu",
        "mynd",
        "gweithio",
    }
)

# Additional soft QA: transparent English loans / calques / awkward probes
# that still have Eurfa paradigms but are poor morphology transfer targets.
EXTRA_OOD_BLOCKLIST = frozenset(
    {
        # English loans / calques / -io probes
        "smocio",
        "smygu",
        "ysmygu",
        "ffacsio",
        "ffônio",
        "ffonio",
        "emailio",
        "ebostio",
        "teipio",
        "pryntio",
        "sgrolio",
        "clicio",
        "clecio",
        "bacsu",
        "bocsio",
        "brwsio",
        "tostio",
        "parcio",
        "stocio",
        "stopio",
        "startio",
        "checkio",
        "postio",
        "testio",
        "linkio",
        "logio",
        "scorio",
        "sgorio",
        "ffilio",
        "fflicio",
        "recordio",
        "editio",
        "downloadio",
        "uploadio",
        "tweetio",
        "ffacebookio",
        "googleio",
        "whatsappio",
        "clocio",
        "trapio",
        "mendio",
        "uwchraddio",
        "dramateiddio",
        "camwario",
        # awkward / scatological / weakly lexicalised
        "ysgothi",
        "tomennu",
        "stumogi",
        "ysglyfaethu",
        "ymgreinio",
        "beichio",
        "byddaru",
        "llwydo",
        "tresio",
        "ailddrafftio",
        "bysio",
        "graeanu",
        "cynio",
        "proffesu",
        "briwio",
        "deialu",
        # OOD review swaps (awkward / literary / weakly usable)
        "corni",
        "sgathru",
        "callio",
        "ymson",
        "carpedu",
        "rhuglo",
    }
)


def _load_exclude_lemmas(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                lemma = (row.get("lemma") or row.get("verb") or "").strip()
                if lemma:
                    out.add(lemma)
    return out


def _eligible_pool(pool: pd.DataFrame, exclude: set[str]) -> pd.DataFrame:
    df = pool.copy()
    if "passes_coverage" in df.columns:
        df = df[df["passes_coverage"].astype(str).str.lower().isin({"true", "1"})]
    # Coverage flags must be true for the three synthetic tenses.
    for col in ("pres6", "past6", "imperf6"):
        if col in df.columns:
            df = df[df[col].astype(str).str.lower().isin({"true", "1"})]
    df = df[df["verbnoun"].astype(str).str.len() > 0]
    blocked = (
        set(exclude)
        | set(EXCLUDED_AUX)
        | set(BLOCKLIST)
        | set(FEWSHOT_EXEMPLAR_LEMMAS)
        | set(EXTRA_OOD_BLOCKLIST)
    )
    df = df[~df["lemma"].isin(blocked)]
    return df.reset_index(drop=True)


def _qa_sample(sample: pd.DataFrame) -> list[str]:
    """Return human-readable warnings for selected verbs (non-fatal)."""
    warnings: list[str] = []
    for _, row in sample.iterrows():
        lemma = str(row["lemma"])
        en = str(row.get("enlemma") or "")
        # Heuristic: English-looking -io loans still in the sample.
        if lemma.endswith("io") and en and en.replace("_", "").isalpha():
            if lemma.rstrip("io") and lemma.rstrip("io") in en.lower().replace(" ", ""):
                warnings.append(f"{lemma} looks like an EN loan ({en})")
    return warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ap.add_argument(
        "--exclude-manifest",
        type=Path,
        action="append",
        default=None,
        help="Manifest(s) whose lemmas must not appear in OOD (default: n150).",
    )
    ap.add_argument("--per-tier", type=int, default=12)
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = ap.parse_args()

    exclude_paths = args.exclude_manifest or [DEFAULT_EXCLUDE]
    if not args.pool.is_file():
        raise SystemExit(f"Missing coverage pool: {args.pool}")
    for path in exclude_paths:
        if not path.is_file():
            raise SystemExit(f"Missing exclude manifest: {path}")

    pool = pd.read_csv(args.pool, keep_default_na=False)
    exclude = _load_exclude_lemmas(exclude_paths)
    eligible = _eligible_pool(pool, exclude)

    print(f"Coverage pool: {len(pool)}")
    print(f"Excluded lemmas: {len(exclude)} from {[str(p) for p in exclude_paths]}")
    print(f"Eligible after coverage + blocklists: {len(eligible)}")
    for tier in TIERS:
        n = int((eligible["tier"] == tier).sum())
        print(f"  {tier}: {n}")
        if n < args.per_tier:
            raise SystemExit(f"Tier {tier!r} has only {n}; need {args.per_tier}")

    sample = sample_tiers(eligible, per_tier=args.per_tier, seed=args.seed)
    sample = sample.assign(lang="cy", experiment=EXPERIMENT_ID, seed=args.seed)
    # Re-assert disjointness.
    overlap = set(sample["lemma"]) & exclude
    if overlap:
        raise SystemExit(f"OOD overlaps train exclude set: {sorted(overlap)}")

    warnings = _qa_sample(sample)
    for w in warnings:
        print(f"QA warning: {w}")

    cols = [
        "lemma",
        "enlemma",
        "verbnoun",
        "lang",
        "cell_id",
        "zipf",
        "tier",
        "freq_rank",
        "raw",
        "per_million",
        "seed",
        "experiment",
    ]
    # Ensure numeric formatting.
    sample = sample.copy()
    sample["zipf"] = sample["zipf"].map(lambda z: round(float(z), 3))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sample[cols].to_csv(args.out, index=False, quoting=csv.QUOTE_MINIMAL)

    summary = {
        "experiment": EXPERIMENT_ID,
        "n_verbs": int(len(sample)),
        "per_tier": args.per_tier,
        "seed": args.seed,
        "exclude_manifests": [str(p) for p in exclude_paths],
        "n_excluded": len(exclude),
        "n_eligible": int(len(eligible)),
        "tiers": {t: int((sample["tier"] == t).sum()) for t in TIERS},
        "zipf_by_tier": {
            t: {
                "min": float(sample.loc[sample["tier"] == t, "zipf"].min()),
                "max": float(sample.loc[sample["tier"] == t, "zipf"].max()),
            }
            for t in TIERS
        },
        "lemmas": {
            t: sample.loc[sample["tier"] == t, "lemma"].tolist() for t in TIERS
        },
        "overlap_with_exclude": [],
        "qa_warnings": warnings,
        "grid": "42 cells/verb (3×6 synthetic + 4×6 periphrastic)",
        "coverage_required": [
            "verbnoun (infin)",
            "synthetic present ×6",
            "synthetic past ×6",
            "synthetic imperfect ×6",
            "periphrastic via bod/gwneud auxiliaries + verbnoun",
        ],
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(sample)} verbs)")
    print(f"Wrote {args.summary}")
    print(sample.groupby("tier").size().to_string())
    print("lemmas:")
    for tier in TIERS:
        lemmas = sample.loc[sample["tier"] == tier, "lemma"].tolist()
        print(f"  {tier}: {', '.join(lemmas)}")


if __name__ == "__main__":
    main()
