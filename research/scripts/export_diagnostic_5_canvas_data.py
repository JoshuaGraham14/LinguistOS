#!/usr/bin/env python3
"""Export Diagnostic 5 breakdown JSON for canvas embedding (read-only)."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ARMS = [
    ("5A", "diagnostic_5a.db", "Baseline"),
    ("5B", "diagnostic_5b.db", "Form-injected"),
    ("5C", "diagnostic_5c.db", "Inject + explicit"),
]

TENSE_ORDER = [
    "present",
    "preterite",
    "imperfect",
    "future",
    "conditional",
    "participle",
]
PERSON_ORDER = ["1st", "2nd", "3rd"]
NUMBER_ORDER = ["singular", "plural"]

_CS_SELECT = """
    json_extract(cs.constraints, '$.tense') AS tense,
    json_extract(cs.constraints, '$.person') AS person,
    json_extract(cs.constraints, '$.number') AS number,
    cs.expected_form
"""


def pct(n: float) -> float:
    return round(n * 100, 1)


def norm_tense(raw: str | None) -> str:
    if not raw:
        return "participle"
    return raw


def main() -> None:
    runs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("research/runs")
    out: dict = {
        "arms": {},
        "tenses": TENSE_ORDER,
        "persons": PERSON_ORDER,
        "numbers": NUMBER_ORDER,
    }

    for arm, fname, label in ARMS:
        path = runs_dir / fname
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        eid = cur.execute("SELECT id FROM experiments").fetchone()[0]

        rows = cur.execute(
            f"""
            SELECT {_CS_SELECT}, se.evaluator_name, se.score
            FROM sentence_evaluations se
            JOIN generated_sentences gs ON gs.id = se.sentence_id
            JOIN constraint_sets cs ON cs.id = gs.constraint_set_id
            WHERE gs.experiment_id = ?
            """,
            (eid,),
        ).fetchall()

        by_tense_ef: dict[str, list[float]] = defaultdict(list)
        by_person_ef: dict[str, list[float]] = defaultdict(list)
        by_number_ef: dict[str, list[float]] = defaultdict(list)
        by_tense_length: dict[str, list[float]] = defaultdict(list)
        ef_all: list[float] = []
        length_all: list[float] = []

        for r in rows:
            tense = norm_tense(r["tense"])
            person = r["person"] or ""
            number = r["number"] or ""
            ev = r["evaluator_name"]
            score = float(r["score"])
            if ev == "expected_form_match":
                ef_all.append(score)
                by_tense_ef[tense].append(score)
                if person:
                    by_person_ef[person].append(score)
                if number:
                    by_number_ef[number].append(score)
            elif ev == "length_in_band":
                length_all.append(score)
                by_tense_length[tense].append(score)

        cell_metrics = cur.execute(
            f"""
            SELECT {_CS_SELECT}, em.metric_name, em.value
            FROM experiment_metrics em
            JOIN constraint_sets cs ON cs.id = em.constraint_set_id
            WHERE em.experiment_id = ? AND em.scope = 'constraint_set'
              AND em.metric_name IN (
                'uniqueness_ratio', 'self_bleu', 'template_rate'
              )
            """,
            (eid,),
        ).fetchall()

        uniq_by_tense: dict[str, list[float]] = defaultdict(list)
        bleu_by_tense: dict[str, list[float]] = defaultdict(list)
        tmpl_by_tense: dict[str, list[float]] = defaultdict(list)
        uniq_vals: list[float] = []
        bleu_vals: list[float] = []
        tmpl_vals: list[float] = []

        for r in cell_metrics:
            tense = norm_tense(r["tense"])
            name = r["metric_name"]
            val = float(r["value"])
            if name == "uniqueness_ratio":
                uniq_by_tense[tense].append(val)
                uniq_vals.append(val)
            elif name == "self_bleu":
                bleu_by_tense[tense].append(val)
                bleu_vals.append(val)
            elif name == "template_rate":
                tmpl_by_tense[tense].append(val)
                tmpl_vals.append(val)

        def mean_map(d: dict[str, list[float]], keys: list[str]) -> list[float]:
            return [pct(sum(d[k]) / len(d[k])) if d.get(k) else 0.0 for k in keys]

        def mean_map_raw(d: dict[str, list[float]], keys: list[str]) -> list[float]:
            return [round(sum(d[k]) / len(d[k]), 3) if d.get(k) else 0.0 for k in keys]

        out["arms"][arm] = {
            "label": label,
            "ef_overall": pct(sum(ef_all) / len(ef_all)) if ef_all else 0.0,
            "length_overall": pct(sum(length_all) / len(length_all)) if length_all else 0.0,
            "uniqueness_mean_cell": round(
                sum(uniq_vals) / len(uniq_vals) * 100, 1
            )
            if uniq_vals
            else 0.0,
            "self_bleu_mean_cell": round(sum(bleu_vals) / len(bleu_vals), 3)
            if bleu_vals
            else 0.0,
            "template_mean_cell": round(sum(tmpl_vals) / len(tmpl_vals), 3)
            if tmpl_vals
            else 0.0,
            "ef_by_tense": mean_map(by_tense_ef, TENSE_ORDER),
            "length_by_tense": mean_map(by_tense_length, TENSE_ORDER),
            "ef_by_person": mean_map(by_person_ef, PERSON_ORDER),
            "ef_by_number": mean_map(by_number_ef, NUMBER_ORDER),
            "uniqueness_by_tense": mean_map_raw(uniq_by_tense, TENSE_ORDER),
            "self_bleu_by_tense": mean_map_raw(bleu_by_tense, TENSE_ORDER),
            "template_by_tense": mean_map_raw(tmpl_by_tense, TENSE_ORDER),
        }
        con.close()

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
