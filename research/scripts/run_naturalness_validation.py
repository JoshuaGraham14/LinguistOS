#!/usr/bin/env python3
"""Run the naturalness evaluators against the minimal-pair validation set.

Produces three artifacts under ``--out-dir``:

  raw.jsonl        — one row per (pair, side) with PPL + judge outputs
  summary.json     — full aggregated report + gate result
  report.md        — human-readable Markdown

Exit code is 0 when the promotion gate passes, 2 otherwise. This is what
the cluster wrapper checks before allowing full Direction 1.2 rescoring.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.evaluation.sentence.fluency_perplexity import FluencyPerplexityEvaluator
from research.evaluation.sentence.naturalness_llm_judge import NaturalnessLlmJudgeEvaluator
from research.evaluation.validation.harness import (
    evaluate_promotion_gate,
    run_validation,
    write_jsonl,
    write_markdown,
    write_summary_json,
)
from research.evaluation.validation.pairs_loader import (
    DEFAULT_PAIRS_YAML,
    load_validation_pairs,
)

EVALUATOR_CHOICES = ("perplexity", "judge", "both")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score the naturalness_pairs.yaml validation set."
    )
    parser.add_argument(
        "--pairs",
        type=Path,
        default=DEFAULT_PAIRS_YAML,
        help="Path to naturalness_pairs.yaml (default: repo default)",
    )
    parser.add_argument(
        "--evaluator",
        choices=EVALUATOR_CHOICES,
        default="both",
        help="Which evaluator to run (default: both)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("research/runs/naturalness_validation"),
        help="Directory to write raw.jsonl, summary.json, report.md",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Optional tag; appended as a subdirectory of --out-dir",
    )
    parser.add_argument(
        "--soft-gate",
        action="store_true",
        help="Exit 0 regardless of gate result (still writes report artifacts)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir if args.tag is None else args.out_dir / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    vset = load_validation_pairs(args.pairs)
    print(
        f"Loaded {len(vset)} minimal pairs from {args.pairs} "
        f"(version={vset.version}, prompt={vset.prompt_version})",
        flush=True,
    )

    ppl_evaluator = None
    judge_evaluator = None
    if args.evaluator in ("perplexity", "both"):
        ppl_evaluator = FluencyPerplexityEvaluator()
    if args.evaluator in ("judge", "both"):
        judge_evaluator = NaturalnessLlmJudgeEvaluator()

    t0 = time.perf_counter()
    report = run_validation(
        vset,
        ppl_evaluator=ppl_evaluator,
        judge_evaluator=judge_evaluator,
    )
    elapsed = (time.perf_counter() - t0) / 60.0

    gate = evaluate_promotion_gate(
        report,
        require_ppl=args.evaluator in ("perplexity", "both"),
        require_judge=args.evaluator in ("judge", "both"),
    )

    raw_path = out_dir / "raw.jsonl"
    summary_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    write_jsonl(report, raw_path)
    write_summary_json(report, gate, summary_path)
    write_markdown(report, gate, md_path)

    print(
        "\n=== Validation summary ===\n"
        f"  PPL pairwise accuracy:   {report.ppl.pairwise_accuracy}\n"
        f"  Judge numeric within-1:  {report.judge.numeric_within_one_rate}\n"
        f"  Judge TFU exact-match:   {report.judge.target_form_use_exact_rate}\n"
        f"  Gate:                    {'PASS' if gate.passed else 'FAIL'}\n"
        f"  Elapsed:                 {elapsed:.1f} min\n"
        f"  Wrote: {raw_path}\n"
        f"         {summary_path}\n"
        f"         {md_path}",
        flush=True,
    )
    if gate.reasons:
        print("  Failure reasons:", flush=True)
        for r in gate.reasons:
            print(f"    - {r}", flush=True)

    if gate.passed or args.soft_gate:
        sys.exit(0)
    sys.exit(2)


if __name__ == "__main__":
    main()
