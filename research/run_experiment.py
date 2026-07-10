"""CLI entry point for research experiments.

Usage:
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default
    python -m research.run_experiment --benchmark spanish_basic --method individual_default --live
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-eval
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-metrics
    python -m research.run_experiment --benchmark spanish_diagnostic_n150 --method diagnostic_5a_hf_qwen3_17b_n10 --live --skip-experiment-group-metrics
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from research.pipeline import run_experiment


def main():
    parser = argparse.ArgumentParser(description="Run a generation experiment")
    parser.add_argument("--benchmark", type=str, required=True,
                        help="Benchmark name (matches <name>.yaml in benchmarks/)")
    parser.add_argument("--method", type=str, required=True,
                        help="Method config name (matches <name>.yaml in methods/)")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live generation (HF local or OpenAI, depending on the method)",
    )
    parser.add_argument("--no-eval", action="store_true", help="Skip per-sentence evaluation (still runs group metrics)")
    parser.add_argument("--no-metrics", action="store_true", help="Skip group metrics and roll-ups")
    parser.add_argument(
        "--skip-experiment-group-metrics",
        action="store_true",
        help=(
            "Compute per-cell (constraint_set) distribution metrics only; "
            "skip pooled experiment-scope metrics (faster on large benchmarks)"
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue the latest incomplete experiment with the same "
            "benchmark+method+live name (skip constraint sets already filled)"
        ),
    )
    parser.add_argument(
        "--resume-experiment-id",
        type=int,
        default=None,
        help="Resume a specific experiment id (skip complete constraint sets)",
    )
    args = parser.parse_args()

    mode = "LIVE" if args.live else "MOCK (canned data)"
    print(f"\n  Running experiment: {args.method} / {args.benchmark} [{mode}]\n")

    run_experiment(
        benchmark_name=args.benchmark,
        method_name=args.method,
        live=args.live,
        evaluate=not args.no_eval,
        metrics=not args.no_metrics,
        experiment_group_metrics=not args.skip_experiment_group_metrics,
        resume=args.resume,
        resume_experiment_id=args.resume_experiment_id,
    )


if __name__ == "__main__":
    main()
