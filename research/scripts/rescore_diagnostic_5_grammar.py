#!/usr/bin/env python3
"""Re-score LanguageTool grammar for completed Diagnostic 5 experiments.

Use when the original run stored grammar_languagetool=0 for all sentences because
LanguageTool cached to a full home directory. Generation and other evaluators are
left unchanged.

Typical cluster usage (one arm, ~30–60 min CPU):

    export PROJECT=/vol/bitbucket/jjg25/LinguistOS
    cd "${PROJECT}"
    source research/.venv/bin/activate
    source research/scripts/cluster/research_cache_env.sh
    export RESEARCH_DB="${PROJECT}/research/runs/diagnostic_5a.db"
    python3 -m research.scripts.rescore_diagnostic_5_grammar --arm 5a

All three arms sequentially: ~1.5–3 hours (46,500 short sentences each; no GPU).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.db.database import get_db_path, init_db
from research.db.database import SessionLocal
from research.evaluation.rescore import (
    DIAGNOSTIC_5_ARMS,
    DIAGNOSTIC_5_DB_FILES,
    find_diagnostic_5_experiment,
    rescore_grammar_languagetool,
)


def _grammar_pass_rate(session, experiment_id: int) -> float | None:
    from sqlalchemy import func

    from research.db.models import GeneratedSentence, SentenceEvaluation
    from research.evaluation.sentence.languagetool import EVALUATOR_NAME

    row = (
        session.query(func.avg(SentenceEvaluation.score))
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == EVALUATOR_NAME,
        )
        .scalar()
    )
    return float(row) if row is not None else None


def _grammar_error_count(session, experiment_id: int) -> int:
    from research.db.models import GeneratedSentence, SentenceEvaluation
    from research.evaluation.sentence.languagetool import EVALUATOR_NAME

    rows = (
        session.query(SentenceEvaluation.details)
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == EVALUATOR_NAME,
        )
        .all()
    )
    return sum(
        1
        for (details,) in rows
        if isinstance(details, dict) and details.get("error")
    )


def _run_arm(
    *,
    arm: str,
    runs_dir: Path,
    db_path: Path | None,
    commit_every: int,
    dry_run: bool,
) -> None:
    if db_path is None:
        db_path = runs_dir / DIAGNOSTIC_5_DB_FILES[arm]
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    os.environ["RESEARCH_DB"] = str(db_path.resolve())
    init_db()
    session = SessionLocal()
    try:
        experiment = find_diagnostic_5_experiment(session, arm)
        before_rate = _grammar_pass_rate(session, experiment.id)
        before_errors = _grammar_error_count(session, experiment.id)
        print(
            f"\n=== Diagnostic {arm.upper()} grammar rescore ===\n"
            f"  DB:         {get_db_path()}\n"
            f"  Experiment: {experiment.name} (id={experiment.id})\n"
            f"  Before:     mean grammar pass {before_rate * 100 if before_rate is not None else 0:.2f}%"
            f"  ({before_errors} LT init errors in details)",
            flush=True,
        )
        if dry_run:
            print("  Dry run — no changes written.", flush=True)
            return

        t0 = time.perf_counter()
        stats = rescore_grammar_languagetool(
            session,
            experiment,
            commit_every=commit_every,
        )
        elapsed_min = (time.perf_counter() - t0) / 60.0
        after_rate = _grammar_pass_rate(session, experiment.id)
        after_errors = _grammar_error_count(session, experiment.id)
        print(
            f"  After:      mean grammar pass {after_rate * 100 if after_rate is not None else 0:.2f}%"
            f"  ({after_errors} LT init errors)\n"
            f"  Elapsed:    {elapsed_min:.1f} min\n"
            f"  Stats:      {stats}",
            flush=True,
        )
        if after_errors:
            print(
                "  WARNING: LT still reporting errors — check LTP_PATH and Java.",
                file=sys.stderr,
                flush=True,
            )
        elif after_rate == 0:
            print(
                "  WARNING: grammar pass rate still 0% — investigate LT setup.",
                file=sys.stderr,
                flush=True,
            )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-score grammar_languagetool for Diagnostic 5 DBs"
    )
    parser.add_argument(
        "--arm",
        action="append",
        choices=sorted(DIAGNOSTIC_5_ARMS),
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
        help="Directory containing diagnostic_5{a,b,c}.db (default: research/runs)",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=500,
        help="Commit progress every N sentences (default: 500)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    arms = args.arm or sorted(DIAGNOSTIC_5_ARMS)
    if args.db is not None and len(arms) != 1:
        parser.error("--db requires exactly one --arm")

    for arm in arms:
        _run_arm(
            arm=arm,
            runs_dir=args.runs_dir,
            db_path=args.db,
            commit_every=args.commit_every,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
