"""CLI entry point for research experiments.

Usage:
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default
    python -m research.run_experiment --benchmark spanish_basic --method individual_default --live
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-eval
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-metrics
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
    parser.add_argument("--live", action="store_true", help="Call OpenAI API (requires OPENAI_API_KEY)")
    parser.add_argument("--no-eval", action="store_true", help="Skip per-sentence evaluation (still runs group metrics)")
    parser.add_argument("--no-metrics", action="store_true", help="Skip group metrics and roll-ups")
    args = parser.parse_args()

    mode = "LIVE (calling OpenAI)" if args.live else "MOCK (canned data)"
    print(f"\n  Running experiment: {args.method} / {args.benchmark} [{mode}]\n")

    run_experiment(
        benchmark_name=args.benchmark,
        method_name=args.method,
        live=args.live,
        evaluate=not args.no_eval,
        metrics=not args.no_metrics,
    )


if __name__ == "__main__":
    main()
