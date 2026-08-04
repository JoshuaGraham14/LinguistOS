#!/usr/bin/env python3
"""Rescore Welsh n10 audit DBs: expected_form_match + naturalness_llm_judge.

Re-runs evaluators on stored sentences (no regeneration). Use after mutation-
aware EF / Welsh judge cy-v2 changes.

Arms (default under research/runs/ on LinguistOS-welsh)::

  welsh_judge_audit_n10_plain.db
  welsh_judge_audit_n10_fewshot.db
  welsh_judge_audit_inject_n1.db

Usage::

  python3 -m research.scripts.rescore_welsh_n10_ef_judge --evaluator both
  python3 -m research.scripts.rescore_welsh_n10_ef_judge --evaluator ef
  python3 -m research.scripts.rescore_welsh_n10_ef_judge --evaluator judge --resume
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
from research.db.database import SessionLocal, init_db
from research.db.models import Experiment
from research.evaluation.rescore import (
    JUDGE_EVALUATOR_NAME,
    rescore_evaluator_for_experiment,
    rescore_naturalness_judge,
)
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION
from research.scripts.audit_welsh_judge_n10 import main as audit_main


@dataclass(frozen=True)
class WelshArm:
    key: str
    db_name: str
    note: str


DEFAULT_ARMS: tuple[WelshArm, ...] = (
    WelshArm("plain", "welsh_judge_audit_n10_plain.db", "zero-shot plain_b"),
    WelshArm("fewshot", "welsh_judge_audit_n10_fewshot.db", "few-shot K=2"),
    WelshArm("inject", "welsh_judge_audit_inject_n1.db", "form inject plain_b"),
    WelshArm(
        "gpt55_plain",
        "welsh_frontier_gpt55_plain_n10.db",
        "GPT-5.5 plain Fix-B frontier",
    ),
)

EF_NAME = ExpectedFormMatchEvaluator().name


def _bind_database(db_path: Path) -> None:
    resolved = db_path.resolve()
    os.environ["RESEARCH_DB"] = str(resolved)
    db.engine.dispose()
    db.engine = db.create_engine_for_path(resolved)
    db.SessionLocal.configure(bind=db.engine)
    init_db()


def _latest_experiment(session) -> Experiment:
    exp = (
        session.query(Experiment)
        .order_by(Experiment.id.desc())
        .first()
    )
    if exp is None:
        raise LookupError("No experiments in this database")
    return exp


def _ef_rate(session, experiment_id: int) -> float | None:
    from sqlalchemy import func

    from research.db.models import GeneratedSentence, SentenceEvaluation

    row = (
        session.query(func.avg(SentenceEvaluation.score))
        .join(GeneratedSentence, SentenceEvaluation.sentence_id == GeneratedSentence.id)
        .filter(
            GeneratedSentence.experiment_id == experiment_id,
            SentenceEvaluation.evaluator_name == EF_NAME,
        )
        .one()
    )
    return float(row[0]) if row[0] is not None else None


def _run_arm(
    arm: WelshArm,
    *,
    runs_dir: Path,
    evaluator: str,
    resume: bool,
    dry_run: bool,
    judge_commit_every: int,
    ef_commit_every: int,
    export_dir: Path,
) -> None:
    db_path = runs_dir / arm.db_name
    if not db_path.is_file():
        raise FileNotFoundError(f"Missing DB for {arm.key}: {db_path}")

    print(f"\n=== {arm.key} ({arm.note}) — {db_path} ===", flush=True)
    if dry_run:
        print("  dry-run: skip", flush=True)
        return

    _bind_database(db_path)
    with SessionLocal() as session:
        experiment = _latest_experiment(session)
        print(
            f"  experiment id={experiment.id} name={experiment.name}",
            flush=True,
        )
        before = _ef_rate(session, experiment.id)
        print(f"  EF before={before}", flush=True)

        if evaluator in {"ef", "both"}:
            t0 = time.time()
            n = rescore_evaluator_for_experiment(
                session,
                experiment,
                ExpectedFormMatchEvaluator(),
                commit_every=ef_commit_every,
                resume=resume and evaluator == "ef",
            )
            after = _ef_rate(session, experiment.id)
            print(
                f"  EF rescored n={n} after={after} "
                f"({time.time() - t0:.1f}s)",
                flush=True,
            )

        if evaluator in {"judge", "both"}:
            print(
                f"  Judge rescore (Welsh prompt {WELSH_PROMPT_VERSION}; "
                f"OpenAI credits)…",
                flush=True,
            )
            t0 = time.time()
            stats = rescore_naturalness_judge(
                session,
                experiment,
                commit_every=judge_commit_every,
                resume=resume,
            )
            print(
                f"  Judge done {stats} ({time.time() - t0:.1f}s)",
                flush=True,
            )

    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / f"welsh_judge_audit_{arm.key}_rescored_summary.json"
    # Reuse audit CLI via argv
    old_argv = sys.argv
    try:
        sys.argv = [
            "audit_welsh_judge_n10",
            "--db",
            str(db_path),
            "--out",
            str(out),
        ]
        audit_main()
    finally:
        sys.argv = old_argv
    print(f"  Wrote {out}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("research/runs"),
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("research/welsh/manifests"),
    )
    parser.add_argument(
        "--evaluator",
        choices=("ef", "judge", "both"),
        default="both",
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=[a.key for a in DEFAULT_ARMS],
        default=[a.key for a in DEFAULT_ARMS],
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ef-commit-every", type=int, default=200)
    parser.add_argument("--judge-commit-every", type=int, default=25)
    args = parser.parse_args()

    wanted = set(args.arms)
    arms = [a for a in DEFAULT_ARMS if a.key in wanted]
    print(
        f"Rescore Welsh n10 | evaluator={args.evaluator} "
        f"arms={[a.key for a in arms]} resume={args.resume} "
        f"judge_prompt={WELSH_PROMPT_VERSION}",
        flush=True,
    )
    for arm in arms:
        _run_arm(
            arm,
            runs_dir=args.runs_dir,
            evaluator=args.evaluator,
            resume=args.resume,
            dry_run=args.dry_run,
            judge_commit_every=args.judge_commit_every,
            ef_commit_every=args.ef_commit_every,
            export_dir=args.export_dir,
        )
    print("\nAll arms done.", flush=True)


if __name__ == "__main__":
    main()
