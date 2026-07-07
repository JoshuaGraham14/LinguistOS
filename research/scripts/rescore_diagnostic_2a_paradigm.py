#!/usr/bin/env python3
"""Re-score Diagnostic 2A paradigm JSON from saved model outputs (no GPU re-run).

Reads ``raw`` text from an existing results file, applies label-aware slot
scoring, and writes updated per-row metrics plus summary.

Usage::

    python3 -m research.scripts.rescore_diagnostic_2a_paradigm
    python3 -m research.scripts.rescore_diagnostic_2a_paradigm \\
        --input docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.paradigm_slot_scoring import (
    SCORING_VERSION,
    score_indicative_paradigm,
    score_participle_form,
)
from research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike import (
    DEFAULT_OUTPUTS,
    is_paradigm_mode,
    normalize_probe_mode,
    summarize,
)


def rescore_row(row: dict) -> dict:
    case = row["case"]
    raw = row.get("raw", "")
    if case.get("is_participle"):
        expected = case["expected"]
        gold = expected[0] if isinstance(expected, list) else expected
        scored = score_participle_form(expected=gold, raw=raw)
    else:
        scored = score_indicative_paradigm(
            expected=case["expected"],
            person_labels=case["person_labels"],
            raw=raw,
        )
        scored["raw"] = raw
    return {
        "case": case,
        "latency_s": row.get("latency_s"),
        **scored,
    }


def rescore_payload(payload: dict) -> dict:
    mode = normalize_probe_mode(payload.get("probe_mode", "diagnostic_2a"))
    if not is_paradigm_mode(mode):
        raise ValueError("This script only re-scores Diagnostic 2A (full paradigm) result files.")
    payload = dict(payload)
    payload["probe_mode"] = "diagnostic_2a"
    payload["scoring_version"] = SCORING_VERSION
    for block in payload.get("by_model", {}).values():
        block["results"] = [rescore_row(r) for r in block["results"]]
    payload["summary"] = summarize(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-score Diagnostic 2A paradigm JSON from saved raw outputs.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_OUTPUTS["diagnostic_2a"],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Defaults to in-place update of --input.",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    updated = rescore_payload(payload)
    out = args.output or args.input
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print(f"Re-scored {args.input} → {out}")
    print(f"scoring_version: {SCORING_VERSION}")
    print(json.dumps(updated["summary"], indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
