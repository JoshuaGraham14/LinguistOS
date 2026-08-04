#!/usr/bin/env python3
"""Live smoke: score Welsh naturalness_pairs_cy.yaml with the LLM judge.

Does NOT write to any experiment DB. Compares judge labels to human_label
on the 15 handcrafted pairs (30 sentences).

Usage:
  set -a && source research/.env && set +a
  export PYTHONPATH=.
  python research/scripts/smoke_welsh_judge_pairs.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.evaluation.sentence.naturalness_llm_judge import (  # noqa: E402
    NaturalnessLlmJudgeEvaluator,
    WELSH_PROMPT_VERSION,
)
from research.evaluation.validation.pairs_loader import (  # noqa: E402
    DEFAULT_WELSH_PAIRS_YAML,
    load_validation_pairs,
)


def _within_one(a: int, b: int) -> bool:
    return abs(a - b) <= 1


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set (source research/.env)", file=sys.stderr)
        return 2

    vset = load_validation_pairs(DEFAULT_WELSH_PAIRS_YAML)
    judge = NaturalnessLlmJudgeEvaluator()
    print(f"pairs={len(vset)} prompt={vset.prompt_version} model={judge.model}")
    assert vset.prompt_version == WELSH_PROMPT_VERSION

    rows: list[dict] = []
    numeric_hits = 0
    numeric_total = 0
    tfu_hits = 0
    tfu_total = 0
    flag_wc_hits = 0
    flag_wc_total = 0

    for pair in vset:
        for side, sent in (("natural", pair.natural), ("awkward", pair.awkward)):
            cons = pair.constraints_for(side)
            result = judge.evaluate(sent.text, "", cons)
            d = result.details or {}
            human = sent.human_label
            err = d.get("error")
            row = {
                "pair_id": pair.pair_id,
                "category": pair.category,
                "side": side,
                "construction": pair.construction,
                "sentence": sent.text,
                "error": err,
                "judge": {
                    "grammaticality": d.get("grammaticality"),
                    "naturalness": d.get("naturalness"),
                    "semantic_coherence": d.get("semantic_coherence"),
                    "target_form_use": d.get("target_form_use"),
                    "flags": d.get("flags"),
                    "rationale": d.get("rationale"),
                    "prompt_version": d.get("prompt_version"),
                },
                "human": human.as_dict(),
            }
            rows.append(row)

            if err:
                print(f"FAIL {pair.pair_id}.{side}: {err}")
                continue

            for axis in ("grammaticality", "naturalness", "semantic_coherence"):
                numeric_total += 1
                if _within_one(int(d[axis]), getattr(human, axis)):
                    numeric_hits += 1
            tfu_total += 1
            if d.get("target_form_use") == human.target_form_use:
                tfu_hits += 1

            if human.target_form_use == "wrong_construction":
                flag_wc_total += 1
                flags = set(d.get("flags") or [])
                if (
                    d.get("target_form_use") == "wrong_construction"
                    and "wrong_construction" in flags
                ):
                    flag_wc_hits += 1

            mark = "ok" if d.get("target_form_use") == human.target_form_use else "TFU≠"
            print(
                f"{mark:4} {pair.pair_id}.{side:8} "
                f"g={d.get('grammaticality')}/{human.grammaticality} "
                f"n={d.get('naturalness')}/{human.naturalness} "
                f"s={d.get('semantic_coherence')}/{human.semantic_coherence} "
                f"tfu={d.get('target_form_use')}/{human.target_form_use} "
                f"flags={d.get('flags')} | {d.get('rationale', '')[:90]}"
            )

    summary = {
        "prompt_version": WELSH_PROMPT_VERSION,
        "model": judge.model,
        "n_sentences": len(rows),
        "numeric_within_one_rate": (
            numeric_hits / numeric_total if numeric_total else None
        ),
        "target_form_use_exact_rate": tfu_hits / tfu_total if tfu_total else None,
        "wrong_construction_detection_rate": (
            flag_wc_hits / flag_wc_total if flag_wc_total else None
        ),
        "numeric_hits": numeric_hits,
        "numeric_total": numeric_total,
        "tfu_hits": tfu_hits,
        "tfu_total": tfu_total,
        "wrong_construction_hits": flag_wc_hits,
        "wrong_construction_total": flag_wc_total,
    }
    out_dir = Path("/tmp")
    out_json = out_dir / "smoke_welsh_judge_pairs.json"
    out_json.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print(json.dumps(summary, indent=2))
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
