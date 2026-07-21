#!/usr/bin/env python3
"""Ad-hoc cross-arm comparison for Direction 4 Neurologic n150 vs Direction 1 refs."""

import json
import sqlite3

ARMS = [
    ("neuro thin_B (b8)", "research/runs/direction_4_n150_thin_B.db"),
    ("neuro b16_a50 (b16)", "research/runs/direction_4_n150_b16_a50.db"),
    ("soft_plain_B (b8)", "research/runs/direction_1p2_n150_soft_plain_B_beams8.db"),
    ("hard_plain_B", "research/runs/direction_1p2_n150_hard_plain_B.db"),
    ("vanilla_plain_B", "research/runs/direction_1p2_n150_vanilla_plain_B.db"),
]

METRICS = [
    ("expected_form_match", "EF"),
    ("grammar_languagetool", "LT"),
    ("length_in_band", "LenBand"),
    ("naturalness_llm_judge", "Judge"),
    ("fluency_perplexity", "PPLscore"),
    ("clause_count", "Clauses"),
]


def raw_ppl(details):
    if not details:
        return None
    try:
        d = json.loads(details)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    for k in ("perplexity", "ppl", "raw_perplexity", "value"):
        if k in d and isinstance(d[k], (int, float)):
            return d[k]
    return None


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


header = f"{'arm':22}"
for _, short in METRICS:
    header += f"{short:>10}"
header += f"{'pplMed':>9}{'uniq%':>8}{'n':>6}"
print(header)
print("-" * len(header))

for label, db in ARMS:
    con = sqlite3.connect(db)
    row = f"{label:22}"
    for name, _ in METRICS:
        v = con.execute(
            "SELECT AVG(score) FROM sentence_evaluations WHERE evaluator_name=?",
            (name,),
        ).fetchone()[0]
        row += f"{v:10.3f}" if v is not None else f"{'-':>10}"
    ppls = [
        raw_ppl(d)
        for (d,) in con.execute(
            "SELECT details FROM sentence_evaluations WHERE evaluator_name='fluency_perplexity'"
        )
    ]
    ppls = [p for p in ppls if p is not None]
    ppl_med = median(ppls)
    ntot = con.execute("SELECT COUNT(*) FROM generated_sentences").fetchone()[0]
    nuniq = con.execute(
        "SELECT COUNT(DISTINCT sentence) FROM generated_sentences"
    ).fetchone()[0]
    uniq = 100 * nuniq / ntot if ntot else 0.0
    row += f"{ppl_med:9.1f}" if ppl_med is not None else f"{'-':>9}"
    row += f"{uniq:8.1f}{ntot:6d}"
    print(row)
