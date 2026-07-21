#!/usr/bin/env python3
"""PPL + LLM-judge rescore for Direction 4 L3/L5 Neurologic spike arms."""

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


SPIKE_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "agree",
            "direction_4_neurologic_agree_hl50_B",
            "direction_4_smoke5_agree.db",
            None,
            "L3 agree morph bans (full paradigm competitors)",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "scene",
            "direction_4_neurologic_thin_scene_hl50_B",
            "direction_4_smoke5_scene.db",
            None,
            "L5 cell scene + diverse final",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "agree_scene",
            "direction_4_neurologic_agree_scene_hl50_B",
            "direction_4_smoke5_agree_scene.db",
            None,
            "L3+L5 agree + scene",
        )
    ),
)

REFERENCE_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "ref_neuro_thin_B",
            "direction_4_neurologic_thin_hl50_B",
            "direction_4_smoke5_neurologic_thin_B.db",
            None,
            "Original Neurologic thin baseline",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_b16_a50",
            "direction_4_neurologic_thin_b16_a50_hl50_B",
            "direction_4_smoke5_b16_a50.db",
            None,
            "Best ablation EF (beams=16)",
        ),
        required=False,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore Direction 4 L3/L5 Neurologic spike smoke5 DBs"
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("research/runs"))
    parser.add_argument("--evaluator", choices=EVALUATOR_CHOICES, default="both")
    parser.add_argument("--ppl-commit-every", type=int, default=200)
    parser.add_argument("--judge-commit-every", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    arms = SPIKE_ARMS + REFERENCE_ARMS
    print(
        f"Direction 4 L3/L5 spike rescore — {len(arms)} arms "
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
