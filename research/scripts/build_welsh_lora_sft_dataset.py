#!/usr/bin/env python3
"""Build Welsh LoRA SFT JSONL by merging synthetic + periphrastic teacher pools.

Sources (per experiment):
  - synthetic cells from the original n150 GPT-5.5 DB (length band short 2–5)
  - periphrastic cells from the peri regen DB (length band short_expanded 4–8)

Experiments:
  - ``lora-form``: inject arm DBs; train prompts include gold surface forms
  - ``lora-no-inject``: plain arm DBs; slot/construction prompt only

Keep rule: EF + target_form_use==correct_main_verb + G,N,S ≥ 4 + length in band
for the construction's sentence_length.

Usage (on cluster)::

    python -m research.scripts.build_welsh_lora_sft_dataset --experiment lora-form
    python -m research.scripts.build_welsh_lora_sft_dataset --experiment lora-no-inject
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from research.evaluation.distribution.tokens import tokenize
from research.evaluation.length_bands import get_band, sentence_length_for_construction
from research.generation.prompt_builder import build_prompt_plain

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "research" / "runs"
CASES = ROOT / "research" / "welsh" / "manifests" / "welsh_cases_n150.csv"
LORA_DIR = ROOT / "research" / "runs" / "lora_welsh"

DB_BY_EXPERIMENT = {
    "lora-no-inject": {
        "synthetic": "welsh_frontier_gpt55_plain_n150.db",
        "periphrastic": "welsh_frontier_gpt55_plain_n150_peri.db",
    },
    "lora-form": {
        "synthetic": "welsh_frontier_gpt55_inject_n150.db",
        "periphrastic": "welsh_frontier_gpt55_inject_n150_peri.db",
    },
}
DEFAULT_OUT = {
    "lora-form": LORA_DIR / "sft_lora_form_n150.jsonl",
    "lora-no-inject": LORA_DIR / "sft_lora_no_inject_n150.jsonl",
}

SQL = """
SELECT
  cs.keyword AS verb,
  cs.expected_form AS expected_form,
  cs.translation AS translation,
  cs.constraints AS constraints_json,
  gs.sentence AS sentence,
  MAX(CASE WHEN se.evaluator_name='expected_form_match' THEN se.score END) AS ef,
  MAX(CASE WHEN se.evaluator_name='naturalness_llm_judge' THEN se.details END) AS details
FROM generated_sentences gs
JOIN constraint_sets cs ON cs.id = gs.constraint_set_id
JOIN sentence_evaluations se ON se.sentence_id = gs.id
WHERE se.evaluator_name IN ('expected_form_match', 'naturalness_llm_judge')
GROUP BY gs.id
"""


def _parse_judge(details: str | None) -> tuple[float, float, float, str] | None:
    if not details:
        return None
    d = json.loads(details)
    g, n, s = d.get("grammaticality"), d.get("naturalness"), d.get("semantic_coherence")
    tfu = d.get("target_form_use")
    if g is None or n is None or s is None or tfu is None:
        return None
    return float(g), float(n), float(s), str(tfu)


def _passes_a_strict(row: dict, *, gmin: float, nmin: float, smin: float) -> bool:
    if row["ef"] is None or float(row["ef"]) < 1.0:
        return False
    parsed = _parse_judge(row["details"])
    if parsed is None:
        return False
    g, n, s, tfu = parsed
    if tfu != "correct_main_verb":
        return False
    return g >= gmin and n >= nmin and s >= smin


def _in_length_band(sentence: str, sentence_length: str) -> bool:
    lo, hi = get_band(sentence_length)
    n = len(tokenize(sentence))
    return lo <= n <= hi


def _constraints_from_row(row: dict) -> dict:
    raw = row.get("constraints_json")
    c = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    # Ensure expected_form is present for prompt/injection.
    if row.get("expected_form") and "expected_form" not in c:
        c["expected_form"] = row["expected_form"]
    return c


def _build_prompt(row: dict, *, inject_form: bool, sentence_length: str) -> str:
    constraints = _constraints_from_row(row)
    return build_prompt_plain(
        keyword=row["verb"],
        translation=row["translation"] or row["verb"],
        target_language="cy",
        constraints=constraints,
        num_candidates=1,
        sentence_length=sentence_length,
        inject_expected_form=row["expected_form"] if inject_form else None,
        require_full_sentence=True,
    )


def _tier_map(cases: Path) -> dict[str, str]:
    if not cases.exists():
        return {}
    with cases.open(encoding="utf-8", newline="") as f:
        return {r["lemma"]: r.get("tier", "UNK") for r in csv.DictReader(f)}


def _load_construction_rows(
    db_path: Path,
    *,
    construction: str,
    gmin: float,
    nmin: float,
    smin: float,
) -> list[dict]:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    kept: list[dict] = []
    for r in con.execute(SQL):
        row = dict(r)
        constraints = _constraints_from_row(row)
        if constraints.get("construction") != construction:
            continue
        if not _passes_a_strict(row, gmin=gmin, nmin=nmin, smin=smin):
            continue
        sentence_length = sentence_length_for_construction(construction)
        if not _in_length_band(row["sentence"], sentence_length):
            continue
        row["constraints"] = constraints
        row["sentence_length"] = sentence_length
        row["construction"] = construction
        row["source_db"] = db_path.name
        kept.append(row)
    con.close()
    return kept


def _balance_stratified(
    rows: list[dict],
    *,
    n: int,
    seed: int,
) -> list[dict]:
    """Select exactly *n* rows while preserving tense/person/tier proportions."""
    if n <= 0 or n >= len(rows):
        return list(rows)

    strata: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        constraints = row["constraints"]
        key = (
            str(constraints.get("tense") or "UNK"),
            str(constraints.get("person") or "UNK"),
            str(constraints.get("number") or "UNK"),
            str(row.get("tier") or "UNK"),
        )
        strata[key].append(row)

    # Largest-remainder proportional allocation gives exactly n overall.
    exact = {key: n * len(group) / len(rows) for key, group in strata.items()}
    quota = {key: min(len(strata[key]), math.floor(value)) for key, value in exact.items()}
    remaining = n - sum(quota.values())
    order = sorted(
        strata,
        key=lambda key: (-(exact[key] - quota[key]), key),
    )
    for key in order:
        if remaining == 0:
            break
        if quota[key] < len(strata[key]):
            quota[key] += 1
            remaining -= 1
    if remaining:
        raise RuntimeError(f"Could not allocate {n} rows across strata ({remaining} left)")

    rng = random.Random(seed)
    selected: list[dict] = []
    for key in sorted(strata):
        group = list(strata[key])
        rng.shuffle(group)
        selected.extend(group[: quota[key]])
    if len(selected) != n:
        raise RuntimeError(f"Balanced sample has {len(selected)} rows; expected {n}")
    return selected


def _stratum_key(row: dict) -> tuple[str, str, str, str]:
    constraints = row["constraints"]
    return (
        str(constraints.get("tense") or "UNK"),
        str(constraints.get("person") or "UNK"),
        str(constraints.get("number") or "UNK"),
        str(row.get("tier") or "UNK"),
    )


def _morphology_key(row: dict) -> tuple[str]:
    constraints = row["constraints"]
    return (str(constraints.get("tense") or "UNK"),)


def _select_with_quotas(
    rows: list[dict],
    *,
    quotas: Counter[tuple[str]],
    seed: int,
) -> list[dict]:
    """Match morphology quotas; preserve tier proportions inside each quota."""
    groups: dict[tuple[str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[_morphology_key(row)].append(row)

    selected: list[dict] = []
    for index, key in enumerate(sorted(quotas)):
        required = quotas[key]
        available = len(groups.get(key, []))
        if available < required:
            raise SystemExit(
                f"Cannot match stratum {key}: need {required}, have {available}"
            )
        selected.extend(
            _balance_stratified(
                groups[key],
                n=required,
                seed=seed + index,
            )
        )
    return selected


def _balance_with_capacity(
    rows: list[dict],
    *,
    n: int,
    capacities: Counter[tuple[str]],
    seed: int,
) -> list[dict]:
    """Balance proportionally, capped by another experiment's morphology pool."""
    groups: dict[tuple[str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[_morphology_key(row)].append(row)

    shared_capacity = {
        key: min(len(group), capacities.get(key, 0))
        for key, group in groups.items()
    }
    if sum(shared_capacity.values()) < n:
        raise SystemExit(
            f"Shared morphology capacity is {sum(shared_capacity.values())}; need {n}"
        )

    exact = {key: n * len(group) / len(rows) for key, group in groups.items()}
    quota = {
        key: min(shared_capacity[key], math.floor(exact[key]))
        for key in groups
    }
    remaining = n - sum(quota.values())
    order = sorted(groups, key=lambda key: (-(exact[key] - quota[key]), key))
    while remaining:
        progressed = False
        for key in order:
            if quota[key] < shared_capacity[key]:
                quota[key] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            raise RuntimeError(f"Could not allocate capacity-capped sample; {remaining} left")

    return _select_with_quotas(rows, quotas=Counter(quota), seed=seed)


def _reference_quotas(
    path: Path,
) -> dict[str, Counter[tuple[str]]]:
    quotas: dict[str, Counter[tuple[str]]] = {
        "synthetic": Counter(),
        "periphrastic": Counter(),
    }
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            construction = str(row["constraints"]["construction"])
            if construction not in quotas:
                raise SystemExit(
                    f"Unexpected construction {construction!r} in {path}"
                )
            quotas[construction][_morphology_key(row)] += 1
    return quotas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment",
        choices=sorted(DEFAULT_OUT),
        required=True,
        help="lora-form = inject teachers; lora-no-inject = plain teachers",
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--min-pairs", type=int, default=2000)
    parser.add_argument("--g-min", type=float, default=4.0)
    parser.add_argument("--n-min", type=float, default=4.0)
    parser.add_argument("--s-min", type=float, default=4.0)
    parser.add_argument(
        "--per-construction",
        type=int,
        default=0,
        help=(
            "If >0, deterministically downsample synthetic and periphrastic "
            "independently to this many rows, stratified by tense/person/tier."
        ),
    )
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument(
        "--match-strata-from",
        type=Path,
        default=None,
        help=(
            "Match exact construction×tense quotas from an existing balanced "
            "JSONL; person, number, and tier remain proportionally stratified."
        ),
    )
    parser.add_argument(
        "--cap-morphology-from",
        type=Path,
        default=None,
        help=(
            "When creating the reference balanced set, cap morphology quotas "
            "by another experiment's full accepted-pool JSONL."
        ),
    )
    args = parser.parse_args()
    if args.match_strata_from and args.cap_morphology_from:
        parser.error("--match-strata-from and --cap-morphology-from are exclusive")

    inject_form = args.experiment == "lora-form"
    if args.output is None:
        base = DEFAULT_OUT[args.experiment]
        if args.per_construction:
            args.output = base.with_name(
                f"{base.stem}_balanced_{args.per_construction}_each{base.suffix}"
            )
        else:
            args.output = base

    db_names = DB_BY_EXPERIMENT[args.experiment]
    tiers = _tier_map(args.cases)
    syn_rows = _load_construction_rows(
        args.runs_dir / db_names["synthetic"],
        construction="synthetic",
        gmin=args.g_min,
        nmin=args.n_min,
        smin=args.s_min,
    )
    peri_rows = _load_construction_rows(
        args.runs_dir / db_names["periphrastic"],
        construction="periphrastic",
        gmin=args.g_min,
        nmin=args.n_min,
        smin=args.s_min,
    )
    for row in syn_rows + peri_rows:
        row["tier"] = tiers.get(row["verb"], "UNK")

    available_by_construction = {
        "synthetic": len(syn_rows),
        "periphrastic": len(peri_rows),
    }
    if args.match_strata_from:
        quotas = _reference_quotas(args.match_strata_from)
        if args.per_construction:
            for construction, construction_quotas in quotas.items():
                total = sum(construction_quotas.values())
                if total != args.per_construction:
                    raise SystemExit(
                        f"Reference has {total} {construction} rows; expected "
                        f"{args.per_construction}."
                    )
        syn_rows = _select_with_quotas(
            syn_rows, quotas=quotas["synthetic"], seed=args.seed
        )
        peri_rows = _select_with_quotas(
            peri_rows, quotas=quotas["periphrastic"], seed=args.seed + 1
        )
    elif args.cap_morphology_from:
        if not args.per_construction:
            parser.error("--cap-morphology-from requires --per-construction")
        capacities = _reference_quotas(args.cap_morphology_from)
        syn_rows = _balance_with_capacity(
            syn_rows,
            n=args.per_construction,
            capacities=capacities["synthetic"],
            seed=args.seed,
        )
        peri_rows = _balance_with_capacity(
            peri_rows,
            n=args.per_construction,
            capacities=capacities["periphrastic"],
            seed=args.seed + 1,
        )
    elif args.per_construction:
        for construction, available in available_by_construction.items():
            if available < args.per_construction:
                raise SystemExit(
                    f"Only {available} {construction} rows; cannot select "
                    f"{args.per_construction}."
                )
        syn_rows = _balance_stratified(
            syn_rows, n=args.per_construction, seed=args.seed
        )
        peri_rows = _balance_stratified(
            peri_rows, n=args.per_construction, seed=args.seed + 1
        )
    rows = syn_rows + peri_rows
    if len(rows) < args.min_pairs:
        raise SystemExit(
            f"Only {len(rows)} pairs (< {args.min_pairs}). Refusing to write."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    by_construction: Counter[str] = Counter()
    by_tense: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_length: Counter[str] = Counter()

    with args.output.open("w", encoding="utf-8") as f:
        for row in sorted(
            rows,
            key=lambda r: (
                r["verb"],
                r["constraints"].get("construction") or "",
                r["constraints"].get("tense") or "",
                str(r["constraints"].get("person") or ""),
                str(r["constraints"].get("number") or ""),
            ),
        ):
            g, n, s, tfu = _parse_judge(row["details"])  # type: ignore[misc]
            sentence_length = row["sentence_length"]
            prompt = _build_prompt(
                row, inject_form=inject_form, sentence_length=sentence_length
            )
            constraints = {
                "tense": row["constraints"].get("tense"),
                "person": row["constraints"].get("person"),
                "number": row["constraints"].get("number"),
                "construction": row["constraints"].get("construction"),
                "expected_form": row["expected_form"],
            }
            if row["constraints"].get("expected_aux"):
                constraints["expected_aux"] = row["constraints"]["expected_aux"]
            if row["constraints"].get("particle"):
                constraints["particle"] = row["constraints"]["particle"]
            if row["constraints"].get("cell_id"):
                constraints["cell_id"] = row["constraints"]["cell_id"]

            tier = row["tier"]

            rec = {
                "experiment": args.experiment,
                "verb": row["verb"],
                "constraints": constraints,
                "prompt": prompt,
                "completion": row["sentence"].strip(),
                "source_db": row["source_db"],
                "sentence_length": sentence_length,
                "token_count": len(tokenize(row["sentence"])),
                "scores": {"G": g, "N": n, "S": s, "tfu": tfu},
                "tier": tier,
                # Balanced Welsh runs deliberately disable Spanish-style
                # oversampling, which would otherwise destroy the 50/50 split.
                "oversample_tags": [],
                "inject_form": inject_form,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            by_construction[row["construction"]] += 1
            by_tense[str(constraints.get("tense") or "UNK")] += 1
            by_tier[tier] += 1
            by_source[row["source_db"]] += 1
            by_length[sentence_length] += 1

    meta = {
        "experiment": args.experiment,
        "inject_form": inject_form,
        "n_pairs": len(rows),
        "filter": "A_strict EF+corrMV+GNS>=4 + length_in_band(by construction)",
        "balance": {
            "per_construction": args.per_construction or None,
            "seed": args.seed,
            "strata": ["tense", "person", "number", "tier"],
            "matched_across_experiments": ["construction", "tense"],
            "matched_strata_from": (
                str(args.match_strata_from) if args.match_strata_from else None
            ),
            "morphology_capacity_from": (
                str(args.cap_morphology_from) if args.cap_morphology_from else None
            ),
            "available_before_downsampling": available_by_construction,
        },
        "dbs": db_names,
        "by_construction": dict(by_construction),
        "by_tense": dict(by_tense),
        "by_tier": dict(by_tier),
        "by_source": dict(by_source),
        "by_sentence_length": dict(by_length),
        "output": str(args.output),
    }
    meta_path = args.output.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"Wrote {len(rows)} pairs → {args.output}")


if __name__ == "__main__":
    main()
