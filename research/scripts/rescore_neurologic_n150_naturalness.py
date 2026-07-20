#!/usr/bin/env python3
"""PPL + LLM-judge rescore for Direction 4 Neurologic n150 arms."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from research.scripts.rescore_direction_1_naturalness import (
    EVALUATOR_CHOICES,
    HeadlineArm,
    _run_one,
)


@dataclass(frozen=True)
class RescoreArm:
    arm: HeadlineArm
    required: bool = True


NEURO_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "thin_B",
            "direction_4_neurologic_thin_n150_B",
            "direction_4_n150_thin_B.db",
            None,
            "Neurologic thin baseline (beams=8)",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "b16_a50",
            "direction_4_neurologic_thin_b16_a50_n150_B",
            "direction_4_n150_b16_a50.db",
            None,
            "Neurologic thin beams=16 alpha=50",
        )
    ),
)

REFERENCE_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "ref_soft_plain_B_beams8",
            "direction_1b_soft_plain_n150_B_beams8",
            "direction_1p2_n150_soft_plain_B_beams8.db",
            None,
            "Direction 1.2 soft beams8 reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_hard_plain_B",
            "direction_1a_hard_plain_n150_B",
            "direction_1p2_n150_hard_plain_B.db",
            None,
            "Direction 1.2 hard plain reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_vanilla_plain_B",
            "direction_1_vanilla_plain_n150_B",
            "direction_1p2_n150_vanilla_plain_B.db",
            None,
            "Direction 1.2 vanilla plain reference",
        ),
        required=False,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore Direction 4 Neurologic n150 DBs"
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("research/runs"))
    parser.add_argument("--evaluator", choices=EVALUATOR_CHOICES, default="both")
    parser.add_argument("--ppl-commit-every", type=int, default=200)
    parser.add_argument("--judge-commit-every", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    arms = NEURO_ARMS + REFERENCE_ARMS
    print(
        f"Direction 4 Neurologic n150 rescore — {len(arms)} arms "
        f"(evaluator={args.evaluator})",
        flush=True,
    )
    for item in arms:
        arm = item.arm
        db_path = args.runs_dir / arm.db_name
        if not item.required and not db_path.is_file():
            print(
                f"WARNING: optional reference DB missing; skipping {db_path}",
                file=sys.stderr,
                flush=True,
            )
            continue
        if item.required and not db_path.is_file():
            print(f"ERROR: required DB missing: {db_path}", file=sys.stderr, flush=True)
            raise SystemExit(1)
        _run_one(
            label=arm.key,
            method_name=arm.method_name,
            db_path=db_path,
            experiment_id=arm.experiment_id,
            which=args.evaluator,
            ppl_commit_every=args.ppl_commit_every,
            judge_commit_every=args.judge_commit_every,
            resume=args.resume,
            dry_run=args.dry_run,
            note=arm.note,
        )


if __name__ == "__main__":
    main()
