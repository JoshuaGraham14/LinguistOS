"""Stratified verb selection for Diagnostic 1 (frequency-validated isolation probes).

Samples verbs from the committed census into a 2×3 grid:
  frequency tier (high / mid / low) × irregularity (regular / irregular)

Outputs ``research/evaluation/lexicon/experiment_verbs/manifest_diagnostic_1_n25.csv``
by default.

Usage::

    python -m research.scripts.select_experiment_verbs
    python -m research.scripts.select_experiment_verbs --per-cell 25 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from research.evaluation.lexicon.en_gold_forms import en_past_and_participle
from research.evaluation.lexicon.en_irregular_lemmas import en_past_tense_irregular
from research.evaluation.lexicon.frequency import (
    _actual_es_form,
    _conjugate_es,
    _strip_pronoun,
    in_census,
    is_irregular,
    tier,
    verb_zipf,
    verbs_in_tier,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = (
    ROOT
    / "research"
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_1_n25.csv"
)
D2_OUT_PATH = (
    ROOT
    / "research"
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_2_paradigm_n150.csv"
)
D1_MANIFEST = OUT_PATH
EXPERIMENT_ID = "diagnostic_1"
D2_EXPERIMENT_ID = "diagnostic_2"

TIERS = ("high", "mid", "low")
# Modals have no infinitival past-tense answer for an isolation probe.
_EN_MODALS: frozenset[str] = frozenset({
    "can", "could", "may", "might", "must", "shall", "should", "will", "would", "ought",
})
# Verbs to exclude from English sampling (vulgar, denominal oddities, bad gold forms).
_EN_BLOCKED: frozenset[str] = frozenset({
    "shit",
    "bitter", "letter", "long", "spear",
    "crimson", "manifold", "quirk",
    "sportscast",
})
PROBE_TENSE_ES = "preterite"
PROBE_PERSON = "1st"
PROBE_NUMBER = "singular"
ES_ENDINGS = ("ar", "er", "ir")


def _es_participle(verb: str) -> str | None:
    data = _conjugate_es(verb)
    if data is None:
        return None
    entries = data["moods"].get("participo", {}).get("participo", [])
    for entry in entries:
        chunks = entry.get("c", [])
        if chunks:
            return _strip_pronoun(chunks[0])
    return None


def _es_ending(verb: str) -> str | None:
    for ending in ES_ENDINGS:
        if verb.endswith(ending):
            return ending
    return None


def _es_preterite_1sg_ok(verb: str) -> bool:
    """Reject verbs where verbecc returns an imperfect form for preterite 1sg."""
    pret = _actual_es_form(verb, PROBE_TENSE_ES, PROBE_PERSON, PROBE_NUMBER)
    if pret is None:
        return False
    # Preterite 1sg for -er/-ir ends in -í; -ía is imperfect (verbecc bug on some verbs).
    if pret.endswith("ía"):
        return False
    return True


def _es_candidates(
    tier_name: str,
    *,
    irregular: bool,
    exclude: set[str],
) -> list[str]:
    pool = [v for v in verbs_in_tier(tier_name, "es") if v not in exclude]
    return [
        v for v in pool
        if is_irregular(v, PROBE_TENSE_ES, "es", PROBE_PERSON, PROBE_NUMBER) is irregular
        and _es_preterite_1sg_ok(v)
    ]


def _en_pool(tier_name: str, *, exclude: set[str]) -> list[str]:
    return [
        v for v in verbs_in_tier(tier_name, "en")
        if v not in exclude and v not in _EN_MODALS and v not in _EN_BLOCKED
    ]


def _en_candidates(tier_name: str, *, irregular: bool, exclude: set[str]) -> list[str]:
    pool = _en_pool(tier_name, exclude=exclude)
    return [v for v in pool if en_past_tense_irregular(v) is irregular]


def _en_regular_candidates(tier_name: str, *, exclude: set[str]) -> list[str]:
    pool = _en_pool(tier_name, exclude=exclude)
    return [v for v in pool if not en_past_tense_irregular(v)]


def _sample_es_regular_balanced(
    tier_name: str,
    n: int,
    rng: random.Random,
    exclude: set[str],
) -> list[str]:
    """Prefer a mix of -ar / -er / -ir in regular cells."""
    by_ending: dict[str, list[str]] = {e: [] for e in ES_ENDINGS}
    for v in _es_candidates(tier_name, irregular=False, exclude=exclude):
        ending = _es_ending(v)
        if ending:
            by_ending[ending].append(v)

    picked: list[str] = []
    per = max(1, n // len(ES_ENDINGS))
    for ending in ES_ENDINGS:
        rng.shuffle(by_ending[ending])
        picked.extend(by_ending[ending][:per])

    if len(picked) < n:
        remainder = [
            v for v in _es_candidates(tier_name, irregular=False, exclude=exclude | set(picked))
        ]
        rng.shuffle(remainder)
        picked.extend(remainder[: n - len(picked)])

    return picked[:n]


def _sample_cell(
    lang: str,
    tier_name: str,
    irregular: bool,
    n: int,
    rng: random.Random,
    exclude: set[str],
) -> list[str]:
    if lang == "es" and not irregular:
        return _sample_es_regular_balanced(tier_name, n, rng, exclude)

    if lang == "es":
        pool = _es_candidates(tier_name, irregular=True, exclude=exclude)
    elif irregular:
        pool = _en_candidates(tier_name, irregular=True, exclude=exclude)
    else:
        pool = _en_regular_candidates(tier_name, exclude=exclude)

    if len(pool) < n:
        import warnings

        warnings.warn(
            f"{lang} tier={tier_name} irregular={irregular}: requested {n}, "
            f"capping at pool size {len(pool)}",
            stacklevel=2,
        )
        n = len(pool)
    rng.shuffle(pool)
    return pool[:n]


def _cell_id(tier_name: str, irregular: bool) -> str:
    reg = "irregular" if irregular else "regular"
    return f"{tier_name}_{reg}"


def manifest_row_for_verb(
    verb: str,
    lang: str,
    cell_id: str,
    *,
    seed: int = 42,
    experiment: str = EXPERIMENT_ID,
) -> dict[str, str]:
    """Build one manifest CSV row for *verb* in *cell_id*."""
    z = verb_zipf(verb, lang)
    t = tier(verb, lang)
    row: dict[str, str] = {
        "verb": verb,
        "lang": lang,
        "cell_id": cell_id,
        "zipf": f"{z:.3f}",
        "tier": t,
        "in_census": "yes" if in_census(verb, lang) else "no",
        "seed": str(seed),
        "experiment": experiment,
    }

    if lang == "es":
        irr = is_irregular(verb, PROBE_TENSE_ES, "es", PROBE_PERSON, PROBE_NUMBER)
        pret = _actual_es_form(verb, PROBE_TENSE_ES, PROBE_PERSON, PROBE_NUMBER)
        part = _es_participle(verb)
        ending = _es_ending(verb) or ""
        if pret is None or part is None:
            raise RuntimeError(f"verbecc missing forms for {verb!r}")
        row.update({
            "irregular_probed": "yes" if irr else "no",
            "probed_tense": PROBE_TENSE_ES,
            "probed_person": PROBE_PERSON,
            "probed_number": PROBE_NUMBER,
            "gold_past_1sg": pret,
            "gold_participle": part,
            "ending": ending,
        })
    else:
        irr = en_past_tense_irregular(verb)
        past_forms, part_forms = en_past_and_participle(verb)
        row.update({
            "irregular_probed": "yes" if irr else "no",
            "probed_tense": "past",
            "probed_person": PROBE_PERSON,
            "probed_number": PROBE_NUMBER,
            "gold_past_1sg": past_forms[0],
            "gold_past_1sg_alts": "|".join(past_forms[1:]),
            "gold_participle": part_forms[0],
            "gold_participle_alts": "|".join(part_forms[1:]),
            "ending": "",
        })

    return row


def _build_rows(
    lang: str,
    *,
    per_cell: int,
    seed: int,
) -> list[dict[str, str]]:
    rng = random.Random(seed + (0 if lang == "es" else 1000))
    exclude: set[str] = set()
    rows: list[dict[str, str]] = []

    for tier_name in TIERS:
        for irregular in (False, True):
            verbs = _sample_cell(lang, tier_name, irregular, per_cell, rng, exclude)
            exclude.update(verbs)
            cell = _cell_id(tier_name, irregular)

            for verb in verbs:
                rows.append(manifest_row_for_verb(verb, lang, cell, seed=seed))

    return rows


def _write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "verb", "lang", "cell_id", "zipf", "tier", "irregular_probed", "in_census",
        "probed_tense", "probed_person", "probed_number",
        "gold_past_1sg", "gold_past_1sg_alts", "gold_participle", "gold_participle_alts",
        "ending", "seed", "experiment",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pick_replacement(
    tier_name: str,
    irregular: bool,
    exclude: set[str],
    rng: random.Random,
) -> str:
    if irregular:
        pool = _en_candidates(tier_name, irregular=True, exclude=exclude)
    else:
        pool = _en_regular_candidates(tier_name, exclude=exclude)
    if not pool:
        raise RuntimeError(
            f"No EN replacement for tier={tier_name} irregular={irregular} "
            f"(exclude size {len(exclude)})"
        )
    rng.shuffle(pool)
    return pool[0]


def swap_blocked_en_verbs(rows: list[dict[str, str]], *, seed: int) -> list[dict[str, str]]:
    """Replace blocked English verbs in *rows*, keeping other selections unchanged."""
    rng = random.Random(seed + 5000)
    used = {r["verb"] for r in rows if r["lang"] == "en"}
    out: list[dict[str, str]] = []
    swaps: list[tuple[str, str, str]] = []

    for row in rows:
        if row["lang"] != "en" or row["verb"] not in _EN_BLOCKED:
            out.append(row)
            continue
        tier_name = row["cell_id"].split("_")[0]
        irregular = row["cell_id"].endswith("_irregular")
        replacement = _pick_replacement(tier_name, irregular, used | _EN_BLOCKED, rng)
        used.add(replacement)
        seed_val = int(row["seed"])
        out.append(manifest_row_for_verb(
            replacement, "en", row["cell_id"], seed=seed_val,
        ))
        swaps.append((row["verb"], replacement, row["cell_id"]))

    for old, new, cell in swaps:
        print(f"  swapped {old!r} → {new!r} ({cell})")
    return out


def subsample_diagnostic_2_manifest(
    source_rows: list[dict[str, str]],
    *,
    per_cell: int = 25,
    seed: int = 42,
) -> list[dict[str, str]]:
    """Subsample Spanish verbs from a Diagnostic 1 manifest (25 per cell for D2)."""
    es_rows = [r for r in source_rows if r["lang"] == "es"]
    by_cell: dict[str, list[dict[str, str]]] = {}
    for row in es_rows:
        by_cell.setdefault(row["cell_id"], []).append(row)

    rng = random.Random(seed)
    picked: list[dict[str, str]] = []
    for cell_id in sorted(by_cell):
        pool = list(by_cell[cell_id])
        rng.shuffle(pool)
        for row in pool[:per_cell]:
            out = dict(row)
            out["experiment"] = D2_EXPERIMENT_ID
            out["seed"] = str(seed)
            picked.append(out)

    picked.sort(key=lambda r: (r["cell_id"], r["verb"]))
    return picked


def _print_summary(rows: list[dict[str, str]]) -> None:
    from collections import Counter

    langs = sorted({r["lang"] for r in rows})
    print(f"\nWrote {len(rows)} verbs")
    for lang in langs:
        lang_rows = [r for r in rows if r["lang"] == lang]
        print(f"\n{lang.upper()} — {len(lang_rows)} verbs")
        counts = Counter(r["cell_id"] for r in lang_rows)
        for cell in sorted(counts):
            print(f"  {cell}: {counts[cell]}")
        zips = [float(r["zipf"]) for r in lang_rows]
        print(f"  Zipf range: {min(zips):.2f} – {max(zips):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select Diagnostic 1 stratified verb manifest")
    parser.add_argument(
        "--experiment",
        choices=("diagnostic_1", "diagnostic_2"),
        default="diagnostic_1",
        help="diagnostic_2 subsamples Spanish verbs from the D1 manifest",
    )
    parser.add_argument("--per-cell", type=int, default=None, help="Verbs per grid cell")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=D1_MANIFEST,
        help="Source manifest for diagnostic_2 subsample (default: manifest_diagnostic_1_n25.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path",
    )
    parser.add_argument(
        "--swap-blocked",
        action="store_true",
        help="Read --output, swap blocked EN verbs in place, and rewrite",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = D2_OUT_PATH if args.experiment == "diagnostic_2" else OUT_PATH
    if args.per_cell is None:
        args.per_cell = 25

    if args.experiment == "diagnostic_2":
        source_rows = _read_manifest(args.source_manifest)
        rows = subsample_diagnostic_2_manifest(
            source_rows, per_cell=args.per_cell, seed=args.seed,
        )
        _write_manifest(rows, args.output)
        _print_summary(rows)
        print(f"\nManifest: {args.output}")
        return

    if args.swap_blocked:
        path = args.output
        rows = _read_manifest(path)
        print(f"Swapping blocked EN verbs in {path}:")
        rows = swap_blocked_en_verbs(rows, seed=args.seed)
        rows.sort(key=lambda r: (r["lang"], r["cell_id"], r["verb"]))
        _write_manifest(rows, path)
        _print_summary(rows)
        print(f"\nManifest: {path}")
        return

    rows = _build_rows("es", per_cell=args.per_cell, seed=args.seed)
    rows.extend(_build_rows("en", per_cell=args.per_cell, seed=args.seed))
    rows.sort(key=lambda r: (r["lang"], r["cell_id"], r["verb"]))

    _write_manifest(rows, args.output)
    _print_summary(rows)
    print(f"\nManifest: {args.output}")


if __name__ == "__main__":
    main()
