#!/usr/bin/env python3
"""Read-only summary of Diagnostic 5 cluster DBs (5A/5B/5C)."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ARMS = [
    ("5A", "diagnostic_5a.db", "baseline"),
    ("5B", "diagnostic_5b.db", "form_injected"),
    ("5C", "diagnostic_5c.db", "form_injected_explicit"),
]

EVALUATORS = ("expected_form_match", "grammar_languagetool", "length_in_band")
PASS_METRICS = tuple(f"pass_rate::{e}" for e in EVALUATORS)


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def analyze_db(db_path: Path) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    eid, name, status, created, completed = cur.execute(
        "SELECT id, name, status, created_at, completed_at FROM experiments"
    ).fetchone()
    cells = cur.execute(
        "SELECT COUNT(DISTINCT constraint_set_id) FROM generated_sentences WHERE experiment_id=?",
        (eid,),
    ).fetchone()[0]
    sents = cur.execute(
        "SELECT COUNT(*) FROM generated_sentences WHERE experiment_id=?", (eid,)
    ).fetchone()[0]
    evals = cur.execute(
        """
        SELECT COUNT(*) FROM sentence_evaluations se
        JOIN generated_sentences gs ON gs.id = se.sentence_id
        WHERE gs.experiment_id = ?
        """,
        (eid,),
    ).fetchone()[0]
    metrics = cur.execute(
        "SELECT COUNT(*) FROM experiment_metrics WHERE experiment_id=?", (eid,)
    ).fetchone()[0]

    t0, t1 = ts(created), ts(completed)
    wall_h = (t1 - t0).total_seconds() / 3600 if t0 and t1 else None
    gmin, gmax = cur.execute(
        "SELECT MIN(created_at), MAX(created_at) FROM generated_sentences WHERE experiment_id=?",
        (eid,),
    ).fetchone()
    g0, g1 = ts(gmin), ts(gmax)
    gen_h = (g1 - g0).total_seconds() / 3600 if g0 and g1 else None

    # eval timestamp spread (proxy for eval phase)
    emin, emax = cur.execute(
        """
        SELECT MIN(se.created_at), MAX(se.created_at) FROM sentence_evaluations se
        JOIN generated_sentences gs ON gs.id = se.sentence_id
        WHERE gs.experiment_id = ?
        """,
        (eid,),
    ).fetchone()
    e0, e1 = ts(emin), ts(emax)
    eval_h = (e1 - e0).total_seconds() / 3600 if e0 and e1 else None

    # metric timestamp spread
    mmin, mmax = cur.execute(
        "SELECT MIN(created_at), MAX(created_at) FROM experiment_metrics WHERE experiment_id=?",
        (eid,),
    ).fetchone()
    m0, m1 = ts(mmin), ts(mmax)
    metric_h = (m1 - m0).total_seconds() / 3600 if m0 and m1 else None

    row: dict = {
        "experiment_id": eid,
        "name": name,
        "status": status,
        "wall_h": wall_h,
        "gen_h": gen_h,
        "eval_h": eval_h,
        "metric_h": metric_h,
        "cells": cells,
        "sents": sents,
        "evals": evals,
        "metrics": metrics,
    }

    for ev in EVALUATORS:
        row[f"mean_{ev}"] = cur.execute(
            """
            SELECT AVG(se.score) FROM sentence_evaluations se
            JOIN generated_sentences gs ON gs.id = se.sentence_id
            WHERE gs.experiment_id = ? AND se.evaluator_name = ?
            """,
            (eid, ev),
        ).fetchone()[0]

    for mn in PASS_METRICS:
        v = cur.execute(
            """
            SELECT value FROM experiment_metrics
            WHERE experiment_id = ? AND metric_name = ? AND scope = 'experiment'
            """,
            (eid, mn),
        ).fetchone()
        row[mn] = v[0] if v else None

    for mn in (
        "self_bleu_experiment",
        "uniqueness_ratio_experiment",
        "template_rate_experiment",
    ):
        v = cur.execute(
            """
            SELECT value FROM experiment_metrics
            WHERE experiment_id = ? AND metric_name = ? AND scope = 'experiment'
            """,
            (eid, mn),
        ).fetchone()
        row[mn] = v[0] if v else None

    # grammar score distribution (sanity: all-zero often means LT unavailable)
    grammar_dist = cur.execute(
        """
        SELECT se.score, COUNT(*) FROM sentence_evaluations se
        JOIN generated_sentences gs ON gs.id = se.sentence_id
        WHERE gs.experiment_id = ? AND se.evaluator_name = 'grammar_languagetool'
        GROUP BY se.score ORDER BY se.score
        """,
        (eid,),
    ).fetchall()
    row["grammar_dist"] = dict(grammar_dist)

    empty = cur.execute(
        """
        SELECT COUNT(*) FROM generated_sentences
        WHERE experiment_id = ? AND (sentence IS NULL OR sentence = '')
        """,
        (eid,),
    ).fetchone()[0]
    row["empty_sentences"] = empty

    # EF by constraint_set — check for degenerate cells
    ef_rows = cur.execute(
        """
        SELECT gs.constraint_set_id, AVG(se.score) as ef
        FROM sentence_evaluations se
        JOIN generated_sentences gs ON gs.id = se.sentence_id
        WHERE gs.experiment_id = ? AND se.evaluator_name = 'expected_form_match'
        GROUP BY gs.constraint_set_id
        """,
        (eid,),
    ).fetchall()
    ef_vals = [r[1] for r in ef_rows]
    row["ef_cells_all_zero"] = sum(1 for v in ef_vals if v == 0)
    row["ef_cells_all_one"] = sum(1 for v in ef_vals if v == 1.0)
    row["ef_cells_partial"] = sum(1 for v in ef_vals if 0 < v < 1.0)

    con.close()
    return row


def main() -> None:
    runs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("research/runs")
    print("=" * 72)
    print("DIAGNOSTIC 5 RESULTS (read-only)")
    print("=" * 72)

    all_rows = []
    for arm, fname, label in ARMS:
        path = runs_dir / fname
        if not path.exists():
            print(f"\nMISSING: {path}")
            continue
        r = analyze_db(path)
        all_rows.append((arm, label, r))
        print(f"\n--- {arm} ({label}) ---")
        print(f"  experiment: {r['name']} (id={r['experiment_id']}) status={r['status']}")
        print(
            f"  timing: wall={r['wall_h']:.2f}h  gen={r['gen_h']:.2f}h  "
            f"eval={r['eval_h']:.2f}h  metrics={r['metric_h']:.2f}h"
        )
        print(
            f"  counts: cells={r['cells']} sents={r['sents']} "
            f"evals={r['evals']} metric_rows={r['metrics']} empty_sents={r['empty_sentences']}"
        )
        for ev in EVALUATORS:
            print(f"  mean {ev}: {r[f'mean_{ev}']*100:.2f}%")
        for mn in PASS_METRICS:
            v = r[mn]
            if v is not None:
                print(f"  {mn}: {v*100:.2f}%")
        for mn in (
            "self_bleu_experiment",
            "uniqueness_ratio_experiment",
            "template_rate_experiment",
        ):
            if r[mn] is not None:
                print(f"  {mn}: {r[mn]:.4f}")
        if r.get("grammar_dist"):
            print(f"  grammar score dist: {r['grammar_dist']}")
        print(
            f"  EF cell breakdown: all_zero={r['ef_cells_all_zero']} "
            f"partial={r['ef_cells_partial']} all_one={r['ef_cells_all_one']}"
        )

    if len(all_rows) == 3:
        print("\n" + "=" * 72)
        print("CROSS-ARM COMPARISON (expected: 5B/5C EF >> 5A)")
        print("=" * 72)
        hdr = f"{'Arm':<6} {'EF pass%':>10} {'EF mean%':>10} {'Grammar%':>10} {'Length%':>10} {'Self-BLEU':>10}"
        print(hdr)
        for arm, label, r in all_rows:
            print(
                f"{arm:<6} "
                f"{r['pass_rate::expected_form_match']*100:>9.1f}% "
                f"{r['mean_expected_form_match']*100:>9.1f}% "
                f"{r['mean_grammar_languagetool']*100:>9.1f}% "
                f"{r['mean_length_in_band']*100:>9.1f}% "
                f"{(r.get('self_bleu_experiment') or 0):>10.4f}"
            )


if __name__ == "__main__":
    main()
