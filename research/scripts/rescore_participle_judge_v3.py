#!/usr/bin/env python3
"""Re-judge participle cells under LLM-judge prompt v3 (He/haber fix).

Default package: the 18 LoRA OOD matrix arms + GPT-5.5 frontier ceiling.

Safety:
  - Backs up each DB to ``<db>.pre_v3_participle.bak`` once (never overwrites
    an existing backup).
  - Archives live ``naturalness_llm_judge`` rows to
    ``naturalness_llm_judge_v2_superseded`` before replacing them.
  - Touches only ``tense == participle`` sentences; finite cells untouched.
  - Idempotent: skips sentences already at ``prompt_version == v3``.

Typical cluster usage::

    python3 -m research.scripts.rescore_participle_judge_v3 --dry-run
    python3 -m research.scripts.rescore_participle_judge_v3
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.db import database as db
from research.db.database import SessionLocal, init_db
from research.db.models import Experiment
from research.evaluation.rescore import rescore_naturalness_judge_for_tense
from research.evaluation.sentence.naturalness_llm_judge import PROMPT_VERSION


@dataclass(frozen=True)
class Arm:
    key: str
    db_path: Path
    note: str = ""


def _default_arms(project: Path) -> list[Arm]:
    runs = project / "research" / "runs"
    frontier = Path(
        "/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55/research/runs"
    )
    ood = [
        "lora_ood_vanilla_base",
        "lora_ood_inject_base",
        "lora_ood_soft_base",
        "lora_ood_soft_inject_base",
        "lora_ood_neuro_base",
        "lora_ood_neuro_inject_base",
        "lora_ood_vanilla_lora",
        "lora_ood_inject_lora",
        "lora_ood_soft_lora",
        "lora_ood_soft_inject_lora",
        "lora_ood_neuro_lora",
        "lora_ood_neuro_inject_lora",
        "lora_ood_vanilla_lora_no_inject",
        "lora_ood_inject_lora_no_inject",
        "lora_ood_soft_lora_no_inject",
        "lora_ood_soft_inject_lora_no_inject",
        "lora_ood_neuro_lora_no_inject",
        "lora_ood_neuro_inject_lora_no_inject",
    ]
    arms = [
        Arm(key=name, db_path=runs / f"{name}.db", note="LoRA OOD matrix")
        for name in ood
    ]
    arms.append(
        Arm(
            key="frontier_ceiling_gpt55_vanilla_ood_n36",
            db_path=frontier / "frontier_ceiling_gpt55_vanilla_ood_n36.db",
            note="GPT-5.5 ceiling",
        )
    )
    return arms


def _bind_database(db_path: Path) -> None:
    resolved = db_path.resolve()
    os.environ["RESEARCH_DB"] = str(resolved)
    db.engine.dispose()
    db.engine = db.create_engine_for_path(resolved)
    db.SessionLocal.configure(bind=db.engine)
    init_db()


def _backup_once(db_path: Path) -> Path | None:
    bak = Path(str(db_path) + ".pre_v3_participle.bak")
    if bak.exists():
        print(f"  backup exists (kept): {bak}", flush=True)
        return bak
    print(f"  copying backup → {bak}", flush=True)
    shutil.copy2(db_path, bak)
    return bak


def _resolve_experiment(session) -> Experiment:
    exp = (
        session.query(Experiment)
        .order_by(Experiment.id.desc())
        .first()
    )
    if exp is None:
        raise LookupError("no experiments in database")
    return exp


def _run_arm(arm: Arm, *, dry_run: bool, commit_every: int) -> dict[str, int]:
    if not arm.db_path.is_file():
        raise FileNotFoundError(f"DB not found: {arm.db_path}")
    print(f"\n=== {arm.key} ===", flush=True)
    print(f"  db={arm.db_path}", flush=True)
    print(f"  note={arm.note}", flush=True)
    if not dry_run:
        _backup_once(arm.db_path)
    _bind_database(arm.db_path)
    session = SessionLocal()
    try:
        exp = _resolve_experiment(session)
        print(
            f"  experiment id={exp.id} name={exp.name!r} status={exp.status}",
            flush=True,
        )
        t0 = time.time()
        stats = rescore_naturalness_judge_for_tense(
            session,
            exp,
            tense="participle",
            commit_every=commit_every,
            refresh_rollups=not dry_run,
            dry_run=dry_run,
        )
        print(f"  wall_s={time.time() - t0:.1f} stats={stats}", flush=True)
        return stats
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path(os.environ.get("PROJECT", "/vol/bitbucket/jjg25/LinguistOS")),
        help="LinguistOS project root on the cluster",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Optional arm keys to run (default: full 18+GPT package)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count candidates only; no backups, archives, or API calls",
    )
    parser.add_argument("--commit-every", type=int, default=10)
    args = parser.parse_args(argv)

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    arms = _default_arms(args.project.resolve())
    if args.only:
        wanted = set(args.only)
        arms = [a for a in arms if a.key in wanted]
        missing = wanted - {a.key for a in arms}
        if missing:
            print(f"ERROR: unknown arms: {sorted(missing)}", file=sys.stderr)
            return 1

    print(f"prompt_version={PROMPT_VERSION}")
    print(f"arms={len(arms)} dry_run={args.dry_run}")
    failures: list[str] = []
    for arm in arms:
        try:
            _run_arm(arm, dry_run=args.dry_run, commit_every=args.commit_every)
        except Exception as exc:  # noqa: BLE001 — keep going across arms
            print(f"  FAILED {arm.key}: {exc}", flush=True)
            failures.append(arm.key)

    print("\n=== summary ===")
    print(f"ok={len(arms) - len(failures)}/{len(arms)}")
    if failures:
        print(f"failed={failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
