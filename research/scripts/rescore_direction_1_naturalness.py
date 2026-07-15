#!/usr/bin/env python3
"""Re-score naturalness evaluators for Direction 1 / 1.2 per-arm DBs.

Runs one or both of:

  fluency_perplexity        Salamandra-2b causal LM (BF16, CUDA if available)
  naturalness_llm_judge     OpenAI Chat Completions (gpt-5.4-mini by default)

Uses the same per-arm DB layout as ``rescore_direction_1_grammar.py``.

Typical cluster usage (headline smoke5 table)::

    python3 -m research.scripts.rescore_direction_1_naturalness \\
        --preset headline_smoke5 --evaluator both
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.db import database as db
from research.db.database import SessionLocal, get_db_path, init_db
from research.db.models import Experiment, GeneratedSentence, SentenceEvaluation
from research.evaluation.rescore import (
    JUDGE_EVALUATOR_NAME,
    PPL_EVALUATOR_NAME,
    rescore_fluency_perplexity,
    rescore_naturalness_judge,
)


def _bind_database(db_path: Path) -> None:
    """Point the global engine/session at *db_path*.

    Setting ``RESEARCH_DB`` alone is NOT enough here: the engine in
    ``research.db.database`` is created at import time, so an env change
    made after import silently keeps the old binding. Rebind explicitly
    so each ``--arm`` iteration writes to its own per-arm file.
    """
    resolved = db_path.resolve()
    os.environ["RESEARCH_DB"] = str(resolved)  # keeps get_db_path() honest in logs
    db.engine.dispose()
    db.engine = db.create_engine_for_path(resolved)
    db.SessionLocal.configure(bind=db.engine)
    init_db()


# Legacy D1.1 / planned full-hl50 arm → method map (kept for --arm use).
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


@dataclass(frozen=True)
class HeadlineArm:
    """One locked rescore arm (smoke5 headline or n150 Fix-B headline)."""

    key: str
    method_name: str
    db_name: str
    experiment_id: int | None
    note: str = ""


# Locked to the user's headline Form/LT table. Hard force uses the smaller
# 2-verb smoke DB because direction_1p2_smoke5_hard_plain.db is empty.
HEADLINE_SMOKE5_ARMS: tuple[HeadlineArm, ...] = (
    HeadlineArm(
        key="vanilla_plain_B",
        method_name="direction_1_vanilla_plain_hl50_B",
        db_name="direction_1p2_smoke5_vanilla_plain_B.db",
        experiment_id=1,  # eid 2 is a duplicate run; prefer the first
        note="Greedy control",
    ),
    HeadlineArm(
        key="soft_plain",
        method_name="direction_1b_soft_plain_hl50",
        db_name="direction_1p2_smoke5_soft_plain.db",
        experiment_id=1,
        note="Soft bias only",
    ),
    HeadlineArm(
        key="soft_plain_B",
        method_name="direction_1b_soft_plain_hl50_B",
        db_name="direction_1p2_smoke5_soft_plain_B.db",
        experiment_id=1,
        note="Soft + better sentence prompt",
    ),
    HeadlineArm(
        key="soft_plain_B_beams8",
        method_name="direction_1b_soft_plain_hl50_B_beams8",
        db_name="direction_1p2_smoke5_soft_plain_B_beams8.db",
        experiment_id=1,
        note="Soft + better prompt + beams 8",
    ),
    HeadlineArm(
        key="inject_plain",
        method_name="direction_1_inject_plain_hl50",
        db_name="direction_1p2_smoke5_inject_plain.db",
        experiment_id=1,
        note="Prompt injection only",
    ),
    HeadlineArm(
        key="soft_inject_plain_B",
        method_name="direction_1b_soft_inject_plain_hl50_B",
        db_name="direction_1p2_smoke5_soft_inject_plain_B.db",
        experiment_id=1,
        note="Soft + inject + better prompt",
    ),
    HeadlineArm(
        key="hard_plain_smoke",
        method_name="direction_1a_hard_plain_hl50",
        db_name="direction_1p2_smoke_hard_plain.db",
        experiment_id=1,
        note="Hard force (2-verb smoke; smoke5 hard DB empty)",
    ),
)

# Full spanish_diagnostic_n150 Fix-B headline (all arms share the Fix-B prompt).
# soft_plain_B = beams 4; soft_plain_B_beams8 = beams 8. Optional 4B probe omitted
# by default — add its DB path when that arm finishes.
HEADLINE_N150_B_ARMS: tuple[HeadlineArm, ...] = (
    HeadlineArm(
        key="vanilla_plain_B",
        method_name="direction_1_vanilla_plain_n150_B",
        db_name="direction_1p2_n150_vanilla_plain_B.db",
        experiment_id=None,
        note="Greedy control (Fix B prompt)",
    ),
    HeadlineArm(
        key="inject_plain_B",
        method_name="direction_1_inject_plain_n150_B",
        db_name="direction_1p2_n150_inject_plain_B.db",
        experiment_id=None,
        note="Prompt injection (Fix B prompt)",
    ),
    HeadlineArm(
        key="soft_plain_B",
        method_name="direction_1b_soft_plain_n150_B",
        db_name="direction_1p2_n150_soft_plain_B.db",
        experiment_id=None,
        note="Soft bias + Fix B (beams=4)",
    ),
    HeadlineArm(
        key="soft_plain_B_beams8",
        method_name="direction_1b_soft_plain_n150_B_beams8",
        db_name="direction_1p2_n150_soft_plain_B_beams8.db",
        experiment_id=None,
        note="Soft bias + Fix B (beams=8)",
    ),
    HeadlineArm(
        key="soft_inject_plain_B",
        method_name="direction_1b_soft_inject_plain_n150_B",
        db_name="direction_1p2_n150_soft_inject_plain_B.db",
        experiment_id=None,
        note="Soft + inject + Fix B (beams=4)",
    ),
    HeadlineArm(
        key="hard_plain_B",
        method_name="direction_1a_hard_plain_n150_B",
        db_name="direction_1p2_n150_hard_plain_B.db",
        experiment_id=None,
        note="Hard force + Fix B (beams=4)",
    ),
)

EVALUATOR_CHOICES = ("perplexity", "judge", "both")


def _find_experiment(
    session,
    method_name: str,
    *,
    experiment_id: int | None = None,
) -> Experiment:
    if experiment_id is not None:
        experiment = session.get(Experiment, experiment_id)
        if experiment is None:
            raise LookupError(
                f"No experiment id={experiment_id} in {get_db_path()}"
            )
        needle = f"__{method_name}__live"
        if needle not in experiment.name:
            raise LookupError(
                f"Experiment id={experiment_id} name={experiment.name!r} "
                f"does not contain {needle!r} in {get_db_path()}"
            )
        return experiment

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


def _count_error_rows(session, experiment_id: int, evaluator_name: str) -> int:
    """Rows whose details carry an ``error`` key (API/scorer failures, score 0.0)."""
    rows = (
        session.query(SentenceEvaluation.details)
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == evaluator_name,
        )
        .all()
    )
    return sum(
        1
        for (details,) in rows
        if isinstance(details, dict) and details.get("error")
    )


def _run_one(
    *,
    label: str,
    method_name: str,
    db_path: Path,
    experiment_id: int | None,
    which: str,
    ppl_commit_every: int,
    judge_commit_every: int,
    resume: bool,
    dry_run: bool,
    note: str = "",
) -> None:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if db_path.stat().st_size == 0:
        raise FileNotFoundError(f"Database is empty (0 bytes): {db_path}")

    _bind_database(db_path)
    session = SessionLocal()
    try:
        experiment = _find_experiment(
            session, method_name, experiment_id=experiment_id
        )
        n_sentences = (
            session.query(GeneratedSentence)
            .filter_by(experiment_id=experiment.id)
            .count()
        )
        print(
            f"\n=== Direction 1.2 [{label}] naturalness rescore ({which}) ===\n"
            f"  DB:         {get_db_path()}\n"
            f"  Experiment: {experiment.name} (id={experiment.id})\n"
            f"  Sentences:  {n_sentences}"
            + (f"\n  Note:       {note}" if note else "")
            + (
                "\n  Mode:       resume (keep good rows, re-run missing/error)"
                if resume
                else ""
            ),
            flush=True,
        )
        if dry_run:
            print("  Dry run — no changes written.", flush=True)
            return

        def _report(evaluator_name: str, stats: dict, t0: float) -> None:
            elapsed = (time.perf_counter() - t0) / 60.0
            written = _count_evaluator_rows(session, experiment.id, evaluator_name)
            errors = _count_error_rows(session, experiment.id, evaluator_name)
            print(
                f"  Rows: {written} total, {errors} with errors "
                f"(elapsed {elapsed:.1f} min)\n"
                f"  Stats: {stats}",
                flush=True,
            )
            if errors:
                print(
                    f"  WARNING: {errors} {evaluator_name} rows carry an error "
                    "and scored 0.0 — re-run with --resume to retry them "
                    "before trusting the roll-ups.",
                    file=sys.stderr,
                    flush=True,
                )

        if which in ("perplexity", "both"):
            print("\n  -- fluency_perplexity --", flush=True)
            t0 = time.perf_counter()
            stats = rescore_fluency_perplexity(
                session,
                experiment,
                commit_every=ppl_commit_every,
                resume=resume,
            )
            _report(PPL_EVALUATOR_NAME, stats, t0)

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
                    resume=resume,
                )
                _report(JUDGE_EVALUATOR_NAME, stats, t0)
    finally:
        session.close()


def _run_arm(
    *,
    arm: str,
    runs_dir: Path,
    db_path: Path | None,
    which: str,
    ppl_commit_every: int,
    judge_commit_every: int,
    resume: bool,
    dry_run: bool,
    experiment_id: int | None,
) -> None:
    method_name = DIRECTION_1_ARMS[arm]
    if db_path is None:
        db_path = runs_dir / f"direction_1p2_{arm}.db"
    _run_one(
        label=arm,
        method_name=method_name,
        db_path=db_path,
        experiment_id=experiment_id,
        which=which,
        ppl_commit_every=ppl_commit_every,
        judge_commit_every=judge_commit_every,
        resume=resume,
        dry_run=dry_run,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Offline rescore for the opt-in naturalness evaluators against "
            "Direction 1 / 1.2 per-arm SQLite DBs."
        )
    )
    parser.add_argument(
        "--preset",
        choices=("headline_smoke5", "headline_n150_B"),
        default=None,
        help=(
            "Rescore a locked arm set. headline_smoke5 = D1.2 Form/LT smoke5 "
            "table; headline_n150_B = Fix-B n150 core arms (vanilla/inject/"
            "soft beams4/soft beams8/soft+inject/hard)."
        ),
    )
    parser.add_argument(
        "--arm",
        action="append",
        choices=sorted(DIRECTION_1_ARMS),
        help="Legacy arm to rescore (repeatable; ignored when --preset is set)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Explicit SQLite path (use with a single --arm)",
    )
    parser.add_argument(
        "--experiment-id",
        type=int,
        default=None,
        help="Pin a specific experiment id (use with a single --arm)",
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
        "--resume",
        action="store_true",
        help=(
            "Keep existing successful rows; only score sentences that are "
            "missing a row or whose previous row carries an error. Use after "
            "a crash or partial API failure instead of re-paying for the "
            "whole arm."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.preset in ("headline_smoke5", "headline_n150_B"):
        if args.arm or args.db is not None or args.experiment_id is not None:
            parser.error("--preset cannot be combined with --arm/--db/--experiment-id")
        preset_arms = (
            HEADLINE_SMOKE5_ARMS
            if args.preset == "headline_smoke5"
            else HEADLINE_N150_B_ARMS
        )
        print(
            f"Preset {args.preset} — {len(preset_arms)} arms "
            f"(evaluator={args.evaluator})",
            flush=True,
        )
        for arm in preset_arms:
            _run_one(
                label=arm.key,
                method_name=arm.method_name,
                db_path=args.runs_dir / arm.db_name,
                experiment_id=arm.experiment_id,
                which=args.evaluator,
                ppl_commit_every=args.ppl_commit_every,
                judge_commit_every=args.judge_commit_every,
                resume=args.resume,
                dry_run=args.dry_run,
                note=arm.note,
            )
        return

    arms = args.arm or sorted(DIRECTION_1_ARMS)
    if args.db is not None and len(arms) != 1:
        parser.error("--db requires exactly one --arm")
    if args.experiment_id is not None and len(arms) != 1:
        parser.error("--experiment-id requires exactly one --arm")

    for arm in arms:
        _run_arm(
            arm=arm,
            runs_dir=args.runs_dir,
            db_path=args.db,
            which=args.evaluator,
            ppl_commit_every=args.ppl_commit_every,
            judge_commit_every=args.judge_commit_every,
            resume=args.resume,
            dry_run=args.dry_run,
            experiment_id=args.experiment_id,
        )


if __name__ == "__main__":
    main()
