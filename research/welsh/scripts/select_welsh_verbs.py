"""Stratified Welsh verb selection for the transfer study.

Ranks CorCenCC ``B (v.)`` lemmas by Zipf frequency (derived from CorCenCC
``per_million``, not wordfreq — Welsh is absent from wordfreq), intersects
with Eurfa lemmas that have usable synthetic coverage for the frozen grid,
splits into Zipf terciles, and samples evenly.

Zipf matches the thesis scale:

    Zipf(w) = log10(f(w) * 1e9)
    f(w)    = per_million / 1e6
            => Zipf = log10(per_million) + 3

Frozen grid: synthetic present / past / imperfect × 6 persons, plus
periphrastic present / past / imperfect / future × 6 persons (person marked
on the auxiliary). Lexical synthetic future is omitted — Eurfa only lists
spoken 3sg for ordinary verbs.

Required target-verb coverage:

  - ``infin`` (verbnoun; needed for all periphrastic cells)
  - ``pres`` / ``past`` / ``imperf`` × persons 1s–3p

Usage::

    python -m research.welsh.scripts.select_welsh_verbs
    python -m research.welsh.scripts.select_welsh_verbs --per-tier 50 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
WELSH_DIR = ROOT / "research" / "welsh"
DATA_DIR = WELSH_DIR / "data"
MANIFEST_DIR = WELSH_DIR / "manifests"

DEFAULT_EURFA = DATA_DIR / "eurfa_cylist20131111.csv"
DEFAULT_CORCENCC = DATA_DIR / "corcencc_lemmas.xlsx"

PERSONS = ("1s", "2s", "3s", "1p", "2p", "3p")
SYNTHETIC_FULL = ("pres", "past", "imperf")

# Auxiliaries used in periphrastic templates — not target vocabulary.
EXCLUDED_LEMMAS = frozenset({"bod", "gwneud"})

TIERS = ("high", "mid", "low")
EXPERIMENT_ID = "welsh_transfer"


def _load_eurfa(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.replace({r"\N": pd.NA, "\\N": pd.NA})
    verbs = df[df["pos"].astype(str).str.startswith("v", na=False)].copy()
    verbs["lemma"] = verbs["lemma"].astype(str)
    verbs["tense"] = verbs["tense"].astype("string")
    verbs["number"] = verbs["number"].astype("string")
    verbs["notes"] = verbs["notes"].astype("string")
    verbs["surface"] = verbs["surface"].astype(str)
    return verbs


def _persons_present(frame: pd.DataFrame) -> set[str]:
    return {str(x) for x in frame["number"].dropna().unique()}


def _preferred_surface(frame: pd.DataFrame) -> str | None:
    """Prefer spoken, then short, then unmarked."""
    if frame.empty:
        return None
    for note in ("spoken", "short"):
        hit = frame[frame["notes"] == note]
        if not hit.empty:
            return str(hit.iloc[0]["surface"])
    unmarked = frame[frame["notes"].isna()]
    if not unmarked.empty:
        return str(unmarked.iloc[0]["surface"])
    return str(frame.iloc[0]["surface"])


def eurfa_coverage(verbs: pd.DataFrame) -> pd.DataFrame:
    """One row per lemma with coverage flags and preferred gold snippets."""
    rows: list[dict] = []
    for lemma, g in verbs.groupby("lemma", sort=False):
        if lemma in EXCLUDED_LEMMAS:
            continue
        by_tense = {t: sub for t, sub in g.groupby(g["tense"].fillna(""), sort=False)}
        empty = g.iloc[0:0]
        has_infin = "infin" in by_tense
        verbnoun = None
        if has_infin:
            verbnoun = _preferred_surface(by_tense["infin"])

        syn_ok: dict[str, bool] = {}
        syn_persons: dict[str, str] = {}
        for tense in SYNTHETIC_FULL:
            sub = by_tense.get(tense, empty)
            have = _persons_present(sub)
            syn_ok[tense] = all(p in have for p in PERSONS)
            syn_persons[tense] = ",".join(p for p in PERSONS if p in have)

        fut = by_tense.get("fut", empty)
        fut_have = _persons_present(fut)

        passes = bool(has_infin and verbnoun and all(syn_ok.values()))
        rows.append(
            {
                "lemma": lemma,
                "enlemma": str(g["enlemma"].dropna().iloc[0]) if g["enlemma"].notna().any() else "",
                "has_infin": has_infin,
                "verbnoun": verbnoun or "",
                "pres6": syn_ok["pres"],
                "past6": syn_ok["past"],
                "imperf6": syn_ok["imperf"],
                "fut_persons": ",".join(p for p in PERSONS if p in fut_have),
                "passes_coverage": passes,
                "n_eurfa_rows": int(len(g)),
            }
        )
    return pd.DataFrame(rows)


def load_corcencc_verbs(path: Path) -> pd.DataFrame:
    lem = pd.read_excel(path, sheet_name="trefn safle | rank order")
    # Bilingual headers: rank / lemma / POS / raw / per million / ...
    lem.columns = [
        "rank",
        "lemma",
        "pos",
        "raw",
        "per_million",
        "rank_written",
        "rank_spoken",
        "rank_elang",
        "raw_written",
        "raw_spoken",
        "raw_elang",
    ]
    verbs = lem[lem["pos"].astype(str).str.strip().eq("B (v.)")].copy()
    verbs["lemma"] = verbs["lemma"].astype(str)
    verbs["zipf"] = verbs["per_million"].map(corcencc_zipf)
    verbs = verbs.sort_values(["zipf", "raw", "lemma"], ascending=[False, False, True])
    verbs["freq_rank"] = range(1, len(verbs) + 1)
    return verbs.reset_index(drop=True)


def corcencc_zipf(per_million: float) -> float:
    """Zipf from CorCenCC rate: log10(f * 1e9) with f = per_million / 1e6."""
    pm = float(per_million)
    if pm <= 0:
        return 0.0
    return math.log10(pm) + 3.0


def assign_terciles(pool: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Split by CorCenCC Zipf rank into high / mid / low (equal-count)."""
    n = len(pool)
    if n < 3:
        raise SystemExit(f"Need at least 3 coverage-passing verbs; got {n}")
    # Equal-count terciles on freq_rank (1 = highest Zipf).
    q1, q2 = n // 3, (2 * n) // 3
    out = pool.copy()

    def tier_for_rank(r: int) -> str:
        if r <= q1:
            return "high"
        if r <= q2:
            return "mid"
        return "low"

    out["tier"] = out["freq_rank"].map(tier_for_rank)
    high = out[out["tier"] == "high"]
    mid = out[out["tier"] == "mid"]
    low = out[out["tier"] == "low"]
    # Spanish-shaped tuple: Zipf < low_upper -> low; Zipf >= high_lower -> high.
    # Boundary ties are assigned by rank (see note).
    def r3(x: float | None) -> float | None:
        return None if x is None else round(float(x), 3)

    low_upper = r3(float(low["zipf"].max())) if len(low) else None
    high_lower = r3(float(high["zipf"].min())) if len(high) else None
    cutoffs = {
        "lang": "cy",
        "frequency_source": "CorCenCC lemma frequencies (Yr Amliadur); not wordfreq",
        "zipf_formula": "log10(per_million) + 3  (= log10(f * 1e9), f = per_million/1e6)",
        "n_pool": n,
        "tier_cutoffs_zipf": [low_upper, high_lower],
        "high_rank_max": int(high["freq_rank"].max()) if len(high) else None,
        "mid_rank_max": int(mid["freq_rank"].max()) if len(mid) else None,
        "low_rank_max": int(low["freq_rank"].max()) if len(low) else None,
        "high_zipf_min": r3(float(high["zipf"].min())) if len(high) else None,
        "high_zipf_max": r3(float(high["zipf"].max())) if len(high) else None,
        "mid_zipf_min": r3(float(mid["zipf"].min())) if len(mid) else None,
        "mid_zipf_max": r3(float(mid["zipf"].max())) if len(mid) else None,
        "low_zipf_min": r3(float(low["zipf"].min())) if len(low) else None,
        "low_zipf_max": r3(float(low["zipf"].max())) if len(low) else None,
        "high_raw_min": float(high["raw"].min()) if len(high) else None,
        "mid_raw_min": float(mid["raw"].min()) if len(mid) else None,
        "low_raw_min": float(low["raw"].min()) if len(low) else None,
        "note": (
            "Tiers are equal-count splits on CorCenCC Zipf rank "
            "(1 = most frequent). Assignment is by rank, not hard Zipf "
            "thresholds (boundary ties). Lexical synthetic future is out of "
            "grid; target coverage is infin + pres/past/imperf × 6."
        ),
    }
    return out, cutoffs


def sample_tiers(pool: pd.DataFrame, per_tier: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    parts: list[pd.DataFrame] = []
    for tier in TIERS:
        cell = pool[pool["tier"] == tier]
        if len(cell) < per_tier:
            raise SystemExit(
                f"Tier {tier!r} has only {len(cell)} verbs; need {per_tier}. "
                "Lower --per-tier or relax coverage."
            )
        pick_idx = rng.sample(list(cell.index), per_tier)
        parts.append(cell.loc[sorted(pick_idx)])
    out = pd.concat(parts, ignore_index=True)
    out["seed"] = seed
    out["experiment"] = EXPERIMENT_ID
    out["cell_id"] = out["tier"]  # frequency-only stratification
    out["zipf"] = out["zipf"].map(lambda z: round(float(z), 3))
    return out.sort_values(["tier", "freq_rank", "lemma"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eurfa", type=Path, default=DEFAULT_EURFA)
    ap.add_argument("--corcencc", type=Path, default=DEFAULT_CORCENCC)
    ap.add_argument("--per-tier", type=int, default=50, help="Verbs per frequency tercile")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=Path, default=MANIFEST_DIR)
    args = ap.parse_args()

    if not args.eurfa.is_file():
        raise SystemExit(f"Missing Eurfa CSV: {args.eurfa}")
    if not args.corcencc.is_file():
        raise SystemExit(f"Missing CorCenCC lemmas workbook: {args.corcencc}")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading Eurfa from {args.eurfa} …")
    eurfa_verbs = _load_eurfa(args.eurfa)
    cov = eurfa_coverage(eurfa_verbs)
    n_pass = int(cov["passes_coverage"].sum())
    print(f"Eurfa verb lemmas: {len(cov)}; pass 4×2 coverage: {n_pass}")

    print(f"Loading CorCenCC lemmas from {args.corcencc} …")
    cor = load_corcencc_verbs(args.corcencc)
    print(f"CorCenCC B (v.) lemmas: {len(cor)}")

    merged = cov.merge(cor, on="lemma", how="inner", suffixes=("", "_cor"))
    pool = merged[merged["passes_coverage"]].copy()
    pool["zipf"] = pool["per_million"].map(corcencc_zipf)
    pool = pool.sort_values(["zipf", "raw", "lemma"], ascending=[False, False, True])
    pool["freq_rank"] = range(1, len(pool) + 1)
    print(f"Intersection with coverage: {len(pool)}")

    pool, cutoffs = assign_terciles(pool)
    for tier in TIERS:
        print(f"  {tier}: {int((pool['tier'] == tier).sum())}")
    print(
        f"  Zipf cutoffs [low_upper, high_lower]: "
        f"{cutoffs['tier_cutoffs_zipf']}"
    )

    sample = sample_tiers(pool, per_tier=args.per_tier, seed=args.seed)
    n = len(sample)
    manifest_path = args.out_dir / f"manifest_welsh_n{n}.csv"
    pool_path = args.out_dir / "welsh_coverage_pool.csv"
    cutoffs_path = args.out_dir / "welsh_tier_cutoffs.json"

    pool = pool.copy()
    pool["zipf"] = pool["zipf"].map(lambda z: round(float(z), 3))
    pool_cols = [
        "lemma",
        "enlemma",
        "verbnoun",
        "tier",
        "freq_rank",
        "zipf",
        "raw",
        "per_million",
        "rank",
        "pres6",
        "past6",
        "imperf6",
        "fut_persons",
        "n_eurfa_rows",
        "passes_coverage",
    ]
    sample_cols = [
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
    sample = sample.assign(lang="cy")

    pool[pool_cols].to_csv(pool_path, index=False, quoting=csv.QUOTE_MINIMAL)
    sample[sample_cols].to_csv(manifest_path, index=False, quoting=csv.QUOTE_MINIMAL)
    cutoffs_path.write_text(json.dumps(cutoffs, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {pool_path} ({len(pool)} rows)")
    print(f"Wrote {manifest_path} ({len(sample)} rows)")
    print(f"Wrote {cutoffs_path}")
    print(sample.groupby("tier").size().to_string())


if __name__ == "__main__":
    main()
