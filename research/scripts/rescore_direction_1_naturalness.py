#!/usr/bin/env python3
"""Re-score naturalness evaluators for Direction 1 / 1.2 per-arm DBs.

Runs one or both of:

  fluency_perplexity        Salamandra-2b causal LM (BF16, CUDA if available)
  naturalness_llm_judge     OpenAI Chat Completions (gpt-5.5-mini by default)

Uses the same per-arm DB layout as ``rescore_direction_1_grammar.py``.

Typical cluster usage::

    export PROJECT=/vol/bitbucket/jjg25/LinguistOS
    cd "${PROJECT}"
    source research/.venv/bin/activate
    source research/scripts/cluster/research_cache_env.sh
    export OPENAI_API_KEY=...    # only needed for --judge
    python3 -m research.scripts.rescore_direction_1_naturalness \\
        --arm hard_plain --evaluator perplexity
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.db.database import SessionLocal, get_db_path, init_db
from research.db.models import Experiment, GeneratedSentence, SentenceEvaluation
from research.evaluation.rescore import (
    JUDGE_EVALUATOR_NAME,
    PPL_EVALUATOR_NAME,
    rescore_fluency_perplexity,
    rescore_naturalness_judge,
)

DIRECTION_1_ARMS: dict[str, str] = {
    "vanilla_plain": "direction_1_vanilla_plain_hl50",
    "inject_plain": "direction_1_inject_plain_hl50",
    "inject_json": "direction_1_inject_json_hl50",
    "hard_plain": "direction_1a_hard_plain_hl50",
    "hard_json": "direction_1a_hard_json_hl50",
    "hard_inject_plain": "direction_1a_hard_inject_plain_hl50",
    "soft_plain": "direction_1b_soft_plain_hl50",
    "soft_json": "direction_1b_soft_json_hl50",
}

EVALUATOR_CHOICES = ("perplexity", "judge", "both")


def _find_experiment(session, method_name: str) -> Experiment:
    needle = f"__{method_name}__live"
    experiment = (
        session.query(Experiment)
        .filter(Experiment.name.like(f"%{needle}"))
        .order_by(Experiment.id.desc())
        .first()
    )
    if experiment is None:
        raise LookupError(
            f"No live experiment matching {needle!r} in {get_db_path()}"
        )
    return experiment


def _count_evaluator_rows(session, experiment_id: int, evaluator_name: str) -> int:
    return (
        session.query(SentenceEvaluation)
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == evaluator_name,
        )
        .count()
    )


def _run_arm(
    *,
    arm: str,
    runs_dir: Path,
    db_path: Path | None,
    which: str,
    ppl_commit_every: int,
    judge_commit_every: int,
    limit: int | None,
    dry_run: bool,
) -> None:
    method_name = DIRECTION_1_ARMS[arm]
    if db_path is None:
        db_path = runs_dir / f"direction_1p2_{arm}.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    os.environ["RESEARCH_DB"] = str(db_path.resolve())
    init_db()
    session = SessionLocal()
    try:
        experiment = _find_experiment(session, method_name)
        n_sentences = (
            session.query(GeneratedSentence)
            .filter_by(experiment_id=experiment.id)
            .count()
        )
        print(
            f"\n=== Direction 1.2 [{arm}] naturalness rescore ({which}) ===\n"
            f"  DB:         {get_db_path()}\n"
            f"  Experiment: {experiment.name} (id={experiment.id})\n"
            f"  Sentences:  {n_sentences}",
            flush=True,
        )
        if limit is not None:
            print(f"  Limit:      {limit} (dev sample)")
        if dry_run:
            print("  Dry run — no changes written.", flush=True)
            return

        if which in ("perplexity", "both"):
            print("\n  -- fluency_perplexity --", flush=True)
            t0 = time.perf_counter()
            stats = rescore_fluency_perplexity(
                session,
                experiment,
                commit_every=ppl_commit_every,
            )
            elapsed = (time.perf_counter() - t0) / 60.0
            written = _count_evaluator_rows(session, experiment.id, PPL_EVALUATOR_NAME)
            print(
                f"  Written rows: {written} (elapsed {elapsed:.1f} min)\n"
                f"  Stats: {stats}",
                flush=True,
            )

        if which in ("judge", "both"):
            if not os.environ.get("OPENAI_API_KEY"):
                print(
                    "  WARNING: OPENAI_API_KEY not set; skipping judge rescore.",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print("\n  -- naturalness_llm_judge --", flush=True)
                t0 = time.perf_counter()
                stats = rescore_naturalness_judge(
                    session,
                    experiment,
                    commit_every=judge_commit_every,
                )
                elapsed = (time.perf_counter() - t0) / 60.0
                written = _count_evaluator_rows(
                    session, experiment.id, JUDGE_EVALUATOR_NAME
                )
                print(
                    f"  Written rows: {written} (elapsed {elapsed:.1f} min)\n"
                    f"  Stats: {stats}",
                    flush=True,
                )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Offline rescore for the opt-in naturalness evaluators against "
            "Direction 1 / 1.2 per-arm SQLite DBs."
        )
    )
    parser.add_argument(
        "--arm",
        action="append",
        choices=sorted(DIRECTION_1_ARMS),
        help="Arm to rescore (repeatable; default: all arms)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Explicit SQLite path (use with a single --arm)",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("research/runs"),
        help="Directory containing direction_1p2_*.db (default: research/runs)",
    )
    parser.add_argument(
        "--evaluator",
        choices=EVALUATOR_CHOICES,
        default="both",
        help="Which evaluator to run (default: both)",
    )
    parser.add_argument(
        "--ppl-commit-every",
        type=int,
        default=200,
        help="Commit progress every N sentences for perplexity (default: 200)",
    )
    parser.add_argument(
        "--judge-commit-every",
        type=int,
        default=50,
        help="Commit progress every N sentences for the judge (default: 50)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional cap on sentences per arm — reserved for dev; the actual "
            "underlying scorer runs over every sentence, this flag is only for "
            "display/reporting purposes today."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    arms = args.arm or sorted(DIRECTION_1_ARMS)
    if args.db is not None and len(arms) != 1:
        parser.error("--db requires exactly one --arm")

    for arm in arms:
        _run_arm(
            arm=arm,
            runs_dir=args.runs_dir,
            db_path=args.db,
            which=args.evaluator,
            ppl_commit_every=args.ppl_commit_every,
            judge_commit_every=args.judge_commit_every,
            limit=args.limit,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
