#!/usr/bin/env python3
"""Analyze EF vs judge correct_main_verb discrepancies for GPT-5.5 Welsh plain n10."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(
    "/vol/bitbucket/jjg25/LinguistOS-welsh/research/runs/welsh_frontier_gpt55_plain_n10.db"
)


def parse(x):
    if not x:
        return {}
    if isinstance(x, dict):
        return x
    return json.loads(x)


def norm(t: str | None) -> str:
    return (t or "").casefold().replace("\u2019", "'").strip()


def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT
          s.id AS sid,
          s.sentence,
          cs.keyword,
          cs.expected_form,
          cs.constraints,
          MAX(CASE WHEN se.evaluator_name = 'expected_form_match' THEN se.score END) AS ef,
          MAX(CASE WHEN se.evaluator_name = 'expected_form_match' THEN se.details END) AS ef_details,
          MAX(CASE WHEN se.evaluator_name = 'naturalness_llm_judge' THEN se.details END) AS judge_details
        FROM generated_sentences s
        JOIN constraint_sets cs ON cs.id = s.constraint_set_id
        LEFT JOIN sentence_evaluations se ON se.sentence_id = s.id
        WHERE s.experiment_id = 1
        GROUP BY s.id
        ORDER BY s.id
        """
    ).fetchall()

    disc = []
    ef_pass_not_cmv = []
    reason_c = Counter()

    for r in rows:
        cons = parse(r["constraints"])
        jd = parse(r["judge_details"])
        ed = parse(r["ef_details"])
        tfu = jd.get("target_form_use")
        ef = float(r["ef"] or 0) >= 0.5
        item = {
            "sid": r["sid"],
            "lemma": r["keyword"],
            "sentence": r["sentence"],
            "expected_form": r["expected_form"] or cons.get("expected_form"),
            "alts": cons.get("expected_form_alts") or [],
            "aux": cons.get("expected_aux"),
            "aux_alts": cons.get("expected_aux_alts") or [],
            "construction": cons.get("construction"),
            "tense": cons.get("tense"),
            "person": cons.get("person"),
            "number": cons.get("number"),
            "cell": cons.get("cell_id"),
            "tfu": tfu,
            "flags": jd.get("flags"),
            "g": jd.get("grammaticality"),
            "n": jd.get("naturalness"),
            "s": jd.get("semantic_coherence"),
            "rationale": (jd.get("rationale") or "")[:280],
            "matched_token": ed.get("matched_token"),
            "matched_aux": ed.get("matched_aux"),
            "form_candidates": ed.get("form_candidates"),
            "reason": ed.get("reason"),
            "mutation_policy": ed.get("mutation_policy"),
            "matched_via_mutation": ed.get("matched_via_mutation"),
        }
        if (not ef) and tfu == "correct_main_verb":
            disc.append(item)
            reason_c[ed.get("reason") or "(none)"] += 1
        if ef and tfu and tfu != "correct_main_verb":
            ef_pass_not_cmv.append(item)

    print(f"total={len(rows)}")
    print(f"EF fail + CMV={len(disc)}")
    print(f"EF pass + not CMV={len(ef_pass_not_cmv)}")
    print("EF fail reasons among CMV:")
    for k, v in reason_c.most_common():
        print(f"  {v:3d}  {k}")

    spoken_map = {
        "rydym": ["rydyn", "dyn", "dan", "ydyn"],
        "rydych": ["dych", "dach", "ydych"],
        "rwyf": ["dw", "rwy", "wi", "ydw"],
        "rwyt": ["wyt"],
        "mae": ["ydy", "yw"],
        "maen": ["ydyn"],
        "roeddem": ["roedden", "oedden", "oeddem"],
        "roeddech": ["oeddech"],
        "roeddwn": ["oeddwn"],
        "roeddet": ["oeddet", "roeddet"],
        "roedden": ["oedden"],
        "gwnaethom": ["wnaethom", "naethom", "wnaethon"],
        "gwnes": ["wnes", "nes"],
        "nath": ["wnaeth", "naeth", "gwnaeth"],
        "byddaf": ["bydda"],
        "byddwn": ["byddwn"],
    }

    buckets: Counter[str] = Counter()
    examples: dict[str, list] = defaultdict(list)

    for it in disc:
        sent = norm(it["sentence"])
        toks = re.findall(r"[\w']+", sent, flags=re.UNICODE)
        cands = [norm(x) for x in (it["form_candidates"] or [])]
        hit = any(c in toks for c in cands if c)
        bucket = "other"

        if it["construction"] == "periphrastic":
            auxes = [norm(it["aux"])] + [norm(a) for a in it["aux_alts"]]
            aux_hit = any(a and (a in toks or a in sent) for a in auxes)
            spoken_hit = False
            for a in auxes:
                for sp in spoken_map.get(a, []):
                    if sp in toks:
                        spoken_hit = True
                        break
            used_imperfect_for_past = it["tense"] == "past" and any(
                x in toks
                for x in (
                    "roedd",
                    "roeddwn",
                    "roeddet",
                    "roeddem",
                    "roeddech",
                    "roedden",
                    "oedd",
                    "oeddet",
                    "oeddem",
                    "oeddech",
                    "oedden",
                )
            )
            if used_imperfect_for_past:
                bucket = "model_imperfect_for_gwneud_past"
            elif spoken_hit and not aux_hit:
                bucket = "aux_spoken_variant_not_in_gold"
            elif not hit and it["lemma"] == "rhoi" and (
                "rhodd" in sent or "roi" in toks or "rhoi" in toks
            ):
                bucket = "peri_rhoi_form_variant"
            elif not hit:
                bucket = "peri_form_not_in_candidates"
            elif not aux_hit and not spoken_hit:
                bucket = "peri_aux_mismatch"
            elif hit and (aux_hit or spoken_hit):
                bucket = "peri_pieces_present_ef_still_fail"
            else:
                bucket = "peri_other"
        else:
            # synthetic
            if it["lemma"] == "rhoi" and ("rhodd" in sent or "rho" in sent):
                bucket = "syn_rhoi_rhoddi_doublet"
            elif it["lemma"] == "paratoi" and "parato" in sent:
                bucket = "syn_paratoi_ending_variant"
            elif it["lemma"] == "troi" and "tro" in sent:
                bucket = "syn_troi_ending_variant"
            elif it["lemma"] == "chwerthin" and (
                "chwerth" in sent or "chwardd" in sent
            ):
                bucket = "syn_chwerthin_stem_variant"
            elif hit:
                bucket = "syn_cand_present_ef_fail"
            else:
                bucket = "syn_form_variant_other"

        buckets[bucket] += 1
        if len(examples[bucket]) < 8:
            examples[bucket].append(it)

    print("\nBucketed EF-fail+CMV:")
    for k, v in buckets.most_common():
        print(f"  {v:3d}  {k}")

    for bucket, items in examples.items():
        print(f"\n==== {bucket} (n={buckets[bucket]}) ====")
        for it in items:
            print(
                f"- {it['lemma']} {it['construction']} {it['tense']} "
                f"{it['person']}/{it['number']} cell={it['cell']}"
            )
            print(f"  gold={it['expected_form']} alts={it['alts']}")
            print(f"  aux={it['aux']} aux_alts={it['aux_alts']}")
            print(f"  sent={it['sentence']}")
            print(f"  cands={it['form_candidates']}")
            print(
                f"  matched_token={it['matched_token']} matched_aux={it['matched_aux']} "
                f"reason={it['reason']} mut_policy={it['mutation_policy']}"
            )
            print(
                f"  judge G/N/S={it['g']}/{it['n']}/{it['s']} flags={it['flags']}"
            )
            print(f"  rationale: {it['rationale']}")

    print("\n==== EF pass but not CMV ====")
    for it in ef_pass_not_cmv:
        print(
            f"- tfu={it['tfu']} {it['lemma']} {it['construction']} "
            f"{it['tense']} {it['person']}/{it['number']}"
        )
        print(f"  gold={it['expected_form']} aux={it['aux']}")
        print(f"  sent={it['sentence']}")
        print(f"  rationale: {it['rationale']}")

    # Also dump all 55 as compact CSV-like for full review
    out = Path(
        "/vol/bitbucket/jjg25/LinguistOS-welsh/research/welsh/manifests/"
        "welsh_frontier_gpt55_plain_n10_ef_cmv_discrepancies.json"
    )
    payload = {
        "n_ef_fail_cmv": len(disc),
        "n_ef_pass_not_cmv": len(ef_pass_not_cmv),
        "buckets": dict(buckets),
        "ef_fail_cmv": disc,
        "ef_pass_not_cmv": ef_pass_not_cmv,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    con.close()


if __name__ == "__main__":
    main()
