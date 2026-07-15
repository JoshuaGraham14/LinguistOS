#!/usr/bin/env python3
"""Build form-given LoRA SFT JSONL from scored n150 Fix-B DBs (primary A_strict).

Default pool: soft_plain_B_beams8_qwen4b → vanilla_plain_B_qwen4b →
inject_plain_B → soft_plain_B_beams8 → soft_inject_plain_B
(one best sentence per morphological cell; never hard arms).

Keep rule: EF match + target_form_use==correct_main_verb + G,N,S ≥ 4.

Usage (on cluster, where research/runs/*.db exist)::

    python -m research.scripts.build_lora_sft_dataset
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from research.generation.prompt_builder import build_prompt_plain

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "research" / "runs"
MANIFEST = (
    ROOT
    / "research"
    / "evaluation"
    / "lexicon"
    / "experiment_verbs"
    / "manifest_diagnostic_2_paradigm_n150.csv"
)
DEFAULT_OUT = ROOT / "research" / "runs" / "lora" / "sft_form_given_n150.jsonl"

PRIMARY_ARMS = [
    "soft_plain_B_beams8_qwen4b",
    "vanilla_plain_B_qwen4b",
    "inject_plain_B",
    "soft_plain_B_beams8",
    "soft_inject_plain_B",
]

SQL = """
SELECT
  cs.keyword AS verb,
  cs.expected_form AS expected_form,
  cs.translation AS translation,
  json_extract(cs.constraints, '$.tense') AS tense,
  json_extract(cs.constraints, '$.person') AS person,
  json_extract(cs.constraints, '$.number') AS number,
  gs.sentence AS sentence,
  MAX(CASE WHEN se.evaluator_name='expected_form_match' THEN se.score END) AS ef,
  MAX(CASE WHEN se.evaluator_name='naturalness_llm_judge' THEN se.details END) AS details
FROM generated_sentences gs
JOIN constraint_sets cs ON cs.id = gs.constraint_set_id
JOIN sentence_evaluations se ON se.sentence_id = gs.id
WHERE se.evaluator_name IN ('expected_form_match', 'naturalness_llm_judge')
GROUP BY gs.id
"""


def _slot(person: str | None, number: str | None) -> str:
    if not person or not number:
        return "nonfinite"
    return {
        ("1st", "singular"): "yo",
        ("2nd", "singular"): "tú",
        ("3rd", "singular"): "él/ella",
        ("1st", "plural"): "nosotros",
        ("2nd", "plural"): "vosotros",
        ("3rd", "plural"): "ellos",
    }.get((person, number), f"{person}/{number}")


def _parse_judge(details: str | None) -> tuple[float, float, float, str] | None:
    if not details:
        return None
    d = json.loads(details)
    g, n, s = d.get("grammaticality"), d.get("naturalness"), d.get("semantic_coherence")
    tfu = d.get("target_form_use")
    if g is None or n is None or s is None or tfu is None:
        return None
    return float(g), float(n), float(s), str(tfu)


def _passes(row: dict, *, gmin: float, nmin: float, smin: float) -> bool:
    if row["ef"] is None or float(row["ef"]) < 1.0:
        return False
    parsed = _parse_judge(row["details"])
    if parsed is None:
        return False
    g, n, s, tfu = parsed
    if tfu != "correct_main_verb":
        return False
    return g >= gmin and n >= nmin and s >= smin


def _build_prompt(row: dict) -> str:
    constraints: dict = {"expected_form": row["expected_form"]}
    if row["tense"]:
        constraints["tense"] = row["tense"]
    if row["person"]:
        constraints["person"] = row["person"]
    if row["number"]:
        constraints["number"] = row["number"]
    return build_prompt_plain(
        keyword=row["verb"],
        translation=row["translation"] or row["verb"],
        target_language="es",
        constraints=constraints,
        num_candidates=1,
        sentence_length="short",
        inject_expected_form=row["expected_form"],
        require_full_sentence=True,
    )


def _score(row: dict, arm_idx: int) -> tuple:
    g, n, s, _ = _parse_judge(row["details"])  # type: ignore[misc]
    return (min(g, n, s), n, g, s, -arm_idx)


def build_pool(
    runs_dir: Path,
    arms: list[str],
    *,
    gmin: float = 4.0,
    nmin: float = 4.0,
    smin: float = 4.0,
) -> dict[tuple, tuple]:
    best: dict[tuple, tuple] = {}
    for arm_idx, arm in enumerate(arms):
        path = runs_dir / f"direction_1p2_n150_{arm}.db"
        if not path.exists():
            raise FileNotFoundError(path)
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for r in con.execute(SQL):
            row = dict(r)
            if not _passes(row, gmin=gmin, nmin=nmin, smin=smin):
                continue
            cell = (
                row["verb"],
                row["tense"] or "participle",
                row["person"],
                row["number"],
                row["expected_form"],
            )
            st = _score(row, arm_idx)
            if cell not in best or st > best[cell][0]:
                best[cell] = (st, arm, row)
        con.close()
    return best


def _tier_map(manifest: Path) -> dict[str, str]:
    with manifest.open(encoding="utf-8", newline="") as f:
        return {r["verb"]: r["tier"] for r in csv.DictReader(f)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--min-pairs", type=int, default=2000)
    parser.add_argument("--g-min", type=float, default=4.0)
    parser.add_argument("--n-min", type=float, default=4.0)
    parser.add_argument("--s-min", type=float, default=4.0)
    args = parser.parse_args()

    tiers = _tier_map(args.manifest)
    best = build_pool(
        args.runs_dir,
        PRIMARY_ARMS,
        gmin=args.g_min,
        nmin=args.n_min,
        smin=args.s_min,
    )
    if len(best) < args.min_pairs:
        raise SystemExit(
            f"Only {len(best)} unique pairs (< {args.min_pairs}). Refusing to write."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    by_arm: Counter[str] = Counter()
    by_tense: Counter[str] = Counter()
    by_person: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()

    with args.output.open("w", encoding="utf-8") as f:
        for (_cell, (st, arm, row)) in sorted(
            best.items(), key=lambda kv: (kv[0][0], kv[0][1], str(kv[0][2]), str(kv[0][3]))
        ):
            g, n, s, tfu = _parse_judge(row["details"])  # type: ignore[misc]
            prompt = _build_prompt(row)
            rec = {
                "verb": row["verb"],
                "constraints": {
                    "tense": row["tense"],
                    "person": row["person"],
                    "number": row["number"],
                    "expected_form": row["expected_form"],
                },
                "prompt": prompt,
                "completion": row["sentence"].strip(),
                "source_arm": arm,
                "scores": {"G": g, "N": n, "S": s, "tfu": tfu},
                "tier": tiers.get(row["verb"], "UNK"),
                "oversample_tags": [],
            }
            person = _slot(row["person"], row["number"])
            tense = row["tense"] or "participle"
            tags = []
            if person == "vosotros":
                tags.append("vosotros")
            if tense == "conditional":
                tags.append("conditional")
            if person == "nonfinite" or tense == "participle":
                tags.append("participle")
            if rec["tier"] == "low":
                tags.append("low_zipf")
            rec["oversample_tags"] = tags
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            by_arm[arm] += 1
            by_tense[tense] += 1
            by_person[person] += 1
            by_tier[rec["tier"]] += 1

    meta = {
        "n_pairs": len(best),
        "filter": "A_strict EF+corrMV+GNS>=4",
        "arms": PRIMARY_ARMS,
        "by_arm": dict(by_arm),
        "by_tense": dict(by_tense),
        "by_person": dict(by_person),
        "by_tier": dict(by_tier),
        "output": str(args.output),
    }
    meta_path = args.output.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"Wrote {len(best)} pairs → {args.output}")


if __name__ == "__main__":
    main()
