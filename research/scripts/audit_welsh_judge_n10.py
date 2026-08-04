#!/usr/bin/env python3
"""Summarise Welsh LLM-judge audit DB for human spot-check.

Prints EF / TFU / wrong_construction rates and sample sentences, and writes
a JSON summary for later review.

Usage::

    export RESEARCH_DB=research/runs/welsh_judge_audit_n10.db
    python3 -m research.scripts.audit_welsh_judge_n10 \\
      --db \"$RESEARCH_DB\" \\
      --out research/welsh/manifests/welsh_judge_audit_n10_summary.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _connect(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _latest_experiment(con: sqlite3.Connection) -> int:
    row = con.execute(
        """
        SELECT id FROM experiments
        WHERE name LIKE '%welsh_transfer_n10%'
           OR name LIKE '%welsh_judge_audit%'
           OR name LIKE '%welsh_frontier_gpt55%'
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        row = con.execute("SELECT id FROM experiments ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        raise SystemExit("No experiments in DB")
    return int(row["id"])


def _load_rows(con: sqlite3.Connection, experiment_id: int) -> list[dict[str, Any]]:
    sql = """
    SELECT
      s.id AS sentence_id,
      s.sentence AS sentence,
      cs.constraints AS constraints,
      cs.keyword AS keyword,
      cs.expected_form AS expected_form_col,
      cs.target_language AS target_language,
      MAX(CASE WHEN se.evaluator_name = 'expected_form_match'
               THEN se.score END) AS ef_score,
      MAX(CASE WHEN se.evaluator_name = 'naturalness_llm_judge'
               THEN se.score END) AS judge_score,
      MAX(CASE WHEN se.evaluator_name = 'naturalness_llm_judge'
               THEN se.details END) AS judge_details
    FROM generated_sentences s
    JOIN constraint_sets cs ON cs.id = s.constraint_set_id
    LEFT JOIN sentence_evaluations se ON se.sentence_id = s.id
    WHERE s.experiment_id = ?
    GROUP BY s.id
    ORDER BY s.id
    """
    out: list[dict[str, Any]] = []
    for row in con.execute(sql, (experiment_id,)):
        cons_raw = row["constraints"]
        if isinstance(cons_raw, str):
            cons = json.loads(cons_raw or "{}")
        elif isinstance(cons_raw, dict):
            cons = cons_raw
        else:
            cons = {}
        details: dict[str, Any] = {}
        raw = row["judge_details"]
        if raw:
            if isinstance(raw, dict):
                details = raw
            else:
                try:
                    details = json.loads(raw)
                except json.JSONDecodeError:
                    details = {"parse_error": True, "raw": str(raw)[:200]}
        out.append(
            {
                "sentence_id": row["sentence_id"],
                "sentence": row["sentence"],
                "lemma": cons.get("keyword") or row["keyword"],
                "construction": cons.get("construction"),
                "tense": cons.get("tense"),
                "person": cons.get("person"),
                "number": cons.get("number"),
                "cell_id": cons.get("cell_id"),
                "expected_form": cons.get("expected_form") or row["expected_form_col"],
                "expected_aux": cons.get("expected_aux"),
                "particle": cons.get("particle"),
                "ef_pass": (row["ef_score"] is not None and float(row["ef_score"]) >= 0.5),
                "judge_score": row["judge_score"],
                "judge": details,
            }
        )
    return out


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tfu = Counter()
    flags = Counter()
    by_construction: dict[str, Counter] = defaultdict(Counter)
    ef_pass = 0
    judge_ok = 0
    wrong_construction_examples: list[dict[str, Any]] = []
    disagreement_examples: list[dict[str, Any]] = []  # EF pass but TFU not correct_main_verb
    syn_peri_examples: list[dict[str, Any]] = []

    for r in rows:
        j = r.get("judge") or {}
        if r["ef_pass"]:
            ef_pass += 1
        if j and not j.get("error") and "target_form_use" in j:
            judge_ok += 1
            tfu_val = j["target_form_use"]
            tfu[tfu_val] += 1
            cons = r.get("construction") or "?"
            by_construction[cons][tfu_val] += 1
            for f in j.get("flags") or []:
                flags[f] += 1

            compact = {
                "lemma": r["lemma"],
                "construction": r["construction"],
                "cell_id": r["cell_id"],
                "expected_form": r["expected_form"],
                "expected_aux": r.get("expected_aux"),
                "sentence": r["sentence"],
                "ef_pass": r["ef_pass"],
                "target_form_use": tfu_val,
                "flags": j.get("flags") or [],
                "grammaticality": j.get("grammaticality"),
                "naturalness": j.get("naturalness"),
                "semantic_coherence": j.get("semantic_coherence"),
                "rationale": j.get("rationale"),
            }
            if tfu_val == "wrong_construction" or "wrong_construction" in (j.get("flags") or []):
                if len(wrong_construction_examples) < 25:
                    wrong_construction_examples.append(compact)
            if r["ef_pass"] and tfu_val not in {
                "correct_main_verb",
                "correct_but_not_main_verb",
            }:
                if len(disagreement_examples) < 25:
                    disagreement_examples.append(compact)
            if tfu_val == "wrong_construction" and len(syn_peri_examples) < 15:
                syn_peri_examples.append(compact)

    n = len(rows)
    return {
        "n_sentences": n,
        "ef_pass_rate": ef_pass / n if n else None,
        "judge_parsed_rate": judge_ok / n if n else None,
        "target_form_use": dict(tfu),
        "flags": dict(flags),
        "tfu_by_construction": {k: dict(v) for k, v in by_construction.items()},
        "wrong_construction_examples": wrong_construction_examples,
        "ef_pass_but_not_correct_main_verb": disagreement_examples,
        "prompt_versions": sorted(
            {
                (r.get("judge") or {}).get("prompt_version")
                for r in rows
                if (r.get("judge") or {}).get("prompt_version")
            }
        ),
    }


def _print_report(summary: dict[str, Any]) -> None:
    print(f"sentences={summary['n_sentences']}")
    print(f"EF pass rate={summary['ef_pass_rate']}")
    print(f"judge parsed rate={summary['judge_parsed_rate']}")
    print(f"prompt_versions={summary['prompt_versions']}")
    print("TFU counts:", json.dumps(summary["target_form_use"], indent=2))
    print("Flags:", json.dumps(summary["flags"], indent=2))
    print("TFU by construction:", json.dumps(summary["tfu_by_construction"], indent=2))
    print("\n--- wrong_construction examples ---")
    for ex in summary["wrong_construction_examples"][:10]:
        print(
            f"[{ex['construction']}/{ex['cell_id']}] {ex['lemma']} "
            f"expected={ex['expected_form']} aux={ex.get('expected_aux')}"
        )
        print(f"  sent: {ex['sentence']}")
        print(
            f"  tfu={ex['target_form_use']} flags={ex['flags']} "
            f"g={ex['grammaticality']} n={ex['naturalness']} s={ex['semantic_coherence']}"
        )
        print(f"  rationale: {ex['rationale']}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--experiment-id", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"DB not found: {args.db}")

    con = _connect(args.db)
    try:
        exp_id = args.experiment_id or _latest_experiment(con)
        rows = _load_rows(con, exp_id)
    finally:
        con.close()

    summary = _summarise(rows)
    summary["experiment_id"] = exp_id
    _print_report(summary)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "n_rows_exported": len(rows)}
        # Keep full TFU examples but not all 420 sentences unless asked.
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
