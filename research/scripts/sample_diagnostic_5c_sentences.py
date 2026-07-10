#!/usr/bin/env python3
"""Sample Diagnostic 5C sentences by evaluation outcome (read-only)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def main() -> None:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("research/runs/diagnostic_5c.db")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    eid = cur.execute("SELECT id FROM experiments").fetchone()[0]

    def samples(where: str, limit: int = 5) -> list[dict]:
        rows = cur.execute(
            f"""
            SELECT
              gs.sentence,
              gs.translation,
              cs.keyword,
              json_extract(cs.constraints, '$.tense') AS tense,
              json_extract(cs.constraints, '$.person') AS person,
              json_extract(cs.constraints, '$.number') AS number,
              cs.expected_form,
              ef.score AS ef_score,
              ef.details AS ef_details,
              lb.score AS lb_score,
              lb.details AS lb_details,
              gs.sample_index
            FROM generated_sentences gs
            JOIN constraint_sets cs ON cs.id = gs.constraint_set_id
            JOIN sentence_evaluations ef ON ef.sentence_id = gs.id
              AND ef.evaluator_name = 'expected_form_match'
            JOIN sentence_evaluations lb ON lb.sentence_id = gs.id
              AND lb.evaluator_name = 'length_in_band'
            WHERE gs.experiment_id = ?
              AND {where}
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (eid, limit),
        ).fetchall()
        out = []
        for r in rows:
            ef_d = json.loads(r["ef_details"] or "{}")
            lb_d = json.loads(r["lb_details"] or "{}")
            out.append(
                {
                    "verb": r["keyword"],
                    "tense": r["tense"] or "participle",
                    "person": r["person"] or "",
                    "number": r["number"] or "",
                    "expected_form": r["expected_form"],
                    "sample_index": r["sample_index"],
                    "sentence": r["sentence"],
                    "translation": r["translation"],
                    "ef_pass": r["ef_score"] >= 0.5,
                    "ef_matched": ef_d.get("matched_token"),
                    "ef_reason": ef_d.get("reason"),
                    "length_pass": r["lb_score"] >= 0.5,
                    "token_count": lb_d.get("token_count"),
                    "length_band": f"{lb_d.get('min')}-{lb_d.get('max')}",
                }
            )
        return out

    # uniqueness: find a cell with high uniqueness and show all 10 sentences
    cell = cur.execute(
        """
        SELECT em.constraint_set_id, em.value, em.breakdown
        FROM experiment_metrics em
        WHERE em.experiment_id = ?
          AND em.metric_name = 'uniqueness_ratio'
          AND em.scope = 'constraint_set'
          AND em.value >= 0.9
        ORDER BY RANDOM()
        LIMIT 1
        """,
        (eid,),
    ).fetchone()

    high_uniq_cell: dict | None = None
    if cell:
        cs_id = cell["constraint_set_id"]
        meta = cur.execute(
            """
            SELECT keyword,
                   json_extract(constraints, '$.tense') AS tense,
                   json_extract(constraints, '$.person') AS person,
                   json_extract(constraints, '$.number') AS number,
                   expected_form
            FROM constraint_sets WHERE id = ?
            """,
            (cs_id,),
        ).fetchone()
        sents = cur.execute(
            """
            SELECT sample_index, sentence, translation
            FROM generated_sentences
            WHERE experiment_id = ? AND constraint_set_id = ?
            ORDER BY sample_index
            """,
            (eid, cs_id),
        ).fetchall()
        high_uniq_cell = {
            "uniqueness": cell["value"],
            "verb": meta["keyword"],
            "tense": meta["tense"] or "participle",
            "person": meta["person"] or "",
            "number": meta["number"] or "",
            "expected_form": meta["expected_form"],
            "sentences": [
                {"i": s["sample_index"], "es": s["sentence"], "en": s["translation"]}
                for s in sents
            ],
        }

    # low uniqueness cell for contrast
    low_cell = cur.execute(
        """
        SELECT em.constraint_set_id, em.value
        FROM experiment_metrics em
        WHERE em.experiment_id = ?
          AND em.metric_name = 'uniqueness_ratio'
          AND em.scope = 'constraint_set'
          AND em.value <= 0.5
        ORDER BY em.value ASC
        LIMIT 1
        """,
        (eid,),
    ).fetchone()

    low_uniq_cell: dict | None = None
    if low_cell:
        cs_id = low_cell["constraint_set_id"]
        meta = cur.execute(
            """
            SELECT keyword,
                   json_extract(constraints, '$.tense') AS tense,
                   expected_form
            FROM constraint_sets WHERE id = ?
            """,
            (cs_id,),
        ).fetchone()
        sents = cur.execute(
            """
            SELECT sample_index, sentence
            FROM generated_sentences
            WHERE experiment_id = ? AND constraint_set_id = ?
            ORDER BY sample_index
            """,
            (eid, cs_id),
        ).fetchall()
        low_uniq_cell = {
            "uniqueness": low_cell["value"],
            "verb": meta["keyword"],
            "tense": meta["tense"] or "participle",
            "expected_form": meta["expected_form"],
            "sentences": [s["sentence"] for s in sents],
        }

    result = {
        "ef_pass": samples("ef.score >= 0.5", 6),
        "ef_fail": samples("ef.score < 0.5", 6),
        "length_fail": samples("lb.score < 0.5", 6),
        "length_pass_ef_pass": samples("lb.score >= 0.5 AND ef.score >= 0.5", 4),
        "participle_ef_fail": samples(
            "json_extract(cs.constraints, '$.tense') IS NULL AND ef.score < 0.5",
            5,
        ),
        "length_too_short": samples(
            "lb.score < 0.5 AND CAST(json_extract(lb.details, '$.token_count') AS INTEGER) < 2",
            4,
        ),
        "length_too_long": samples(
            "lb.score < 0.5 AND CAST(json_extract(lb.details, '$.token_count') AS INTEGER) > 5",
            4,
        ),
        "high_uniqueness_cell": high_uniq_cell,
        "low_uniqueness_cell": low_uniq_cell,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    con.close()


if __name__ == "__main__":
    main()
