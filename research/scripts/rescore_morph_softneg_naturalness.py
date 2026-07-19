#!/usr/bin/env python3
"""PPL + LLM-judge rescore for Direction 3b soft-negative thin morph arms.

Additive entry point: does not modify the locked Direction 3 / 1.2 rescore
presets.
"""

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


SOFTNEG_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "softneg_thin_B",
            "direction_1c_soft_morph_softneg_thin_hl50_B",
            "direction_3b_smoke5_softneg_thin_B.db",
            None,
            "Soft + soft-negative thin bans + subject gate",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "softneg_thin_inject_B",
            "direction_1c_soft_morph_softneg_thin_inject_hl50_B",
            "direction_3b_smoke5_softneg_thin_inject_B.db",
            None,
            "Soft + inject + soft-negative thin bans + subject gate",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "softneg_thin_inject_role_B",
            "direction_1c_soft_morph_softneg_thin_inject_role_hl50_B",
            "direction_3b_smoke5_softneg_thin_inject_role_B.db",
            None,
            "Soft + inject + softneg thin + ROOT role resample",
        )
    ),
)

REFERENCE_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "ref_soft_plain_B_beams8",
            "direction_1b_soft_plain_hl50_B_beams8",
            "direction_1p2_smoke5_soft_plain_B_beams8.db",
            1,
            "Primary matched Direction 1.2 soft reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_soft_inject_plain_B",
            "direction_1b_soft_inject_plain_hl50_B",
            "direction_1p2_smoke5_soft_inject_plain_B.db",
            1,
            "Soft + inject Fix-B reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_soft_morph_inject_B",
            "direction_1c_soft_morph_inject_hl50_B",
            "direction_3_smoke5_soft_morph_inject_B.db",
            1,
            "Direction 3 hard-ban soft+inject context",
        ),
        required=False,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore Direction 3b softneg thin smoke5 DBs"
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("research/runs"),
    )
    parser.add_argument(
        "--evaluator",
        choices=EVALUATOR_CHOICES,
        default="both",
    )
    parser.add_argument("--ppl-commit-every", type=int, default=200)
    parser.add_argument("--judge-commit-every", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--new-arms-only",
        action="store_true",
        help="Skip optional reference DBs",
    )
    args = parser.parse_args()

    arms = SOFTNEG_ARMS + (() if args.new_arms_only else REFERENCE_ARMS)
    print(
        f"Direction 3b softneg rescore — {len(arms)} arms "
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
