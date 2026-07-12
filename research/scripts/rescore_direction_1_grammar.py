#!/usr/bin/env python3
"""Re-score LanguageTool grammar for Direction 1 / 1.2 experiments (no regeneration).

Mirrors :mod:`research.scripts.rescore_diagnostic_5_grammar`. Use after the
first pass if grammar came back all-zero (typical cause: `LTP_PATH` not set
or `~/.cache/language_tool_python` disk quota exceeded).

Typical cluster usage::

    export PROJECT=/vol/bitbucket/jjg25/LinguistOS
    cd "${PROJECT}"
    source research/.venv/bin/activate
    source research/scripts/cluster/research_cache_env.sh
    export RESEARCH_DB="${PROJECT}/research/runs/direction_1p2_hard_plain.db"
    python3 -m research.scripts.rescore_direction_1_grammar --arm hard_plain
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
from research.db.models import Experiment
from research.evaluation.rescore import rescore_grammar_languagetool

# arm short name → method_config.name (matches YAMLs under research/methods/baseline/)
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


def _run_arm(
    *,
    arm: str,
    runs_dir: Path,
    db_path: Path | None,
    commit_every: int,
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
        before_rate = _grammar_pass_rate(session, experiment.id)
        before_errors = _grammar_error_count(session, experiment.id)
        print(
            f"\n=== Direction 1.2 [{arm}] grammar rescore ===\n"
            f"  DB:         {get_db_path()}\n"
            f"  Experiment: {experiment.name} (id={experiment.id})\n"
            f"  Before:     mean grammar pass "
            f"{(before_rate or 0) * 100:.2f}% "
            f"({before_errors} LT init errors)",
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
            f"  After:      mean grammar pass "
            f"{(after_rate or 0) * 100:.2f}% ({after_errors} LT init errors)\n"
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
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-score grammar_languagetool for Direction 1.2 DBs"
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
        "--commit-every",
        type=int,
        default=500,
        help="Commit progress every N sentences (default: 500)",
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
            commit_every=args.commit_every,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
