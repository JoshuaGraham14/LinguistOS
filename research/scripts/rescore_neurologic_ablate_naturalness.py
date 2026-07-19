#!/usr/bin/env python3
"""PPL + LLM-judge rescore for Direction 4 Neurologic ablation/tune arms.

Additive entry point. Reuses baseline neuro_thin_B + soft refs when present.
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


ABLATION_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(HeadlineArm("len", "direction_4_neurologic_thin_len_hl50_B", "direction_4_smoke5_len.db", None, "min_new_tokens=6")),
    RescoreArm(HeadlineArm("lam03", "direction_4_neurologic_thin_lam03_hl50_B", "direction_4_smoke5_lam03.db", None, "lambda=0.3")),
    RescoreArm(HeadlineArm("group", "direction_4_neurologic_thin_group_hl50_B", "direction_4_smoke5_group.db", None, "rich clause grouping")),
    RescoreArm(HeadlineArm("prefix", "direction_4_neurologic_thin_prefix_hl50_B", "direction_4_smoke5_prefix.db", None, "prefix automaton")),
    RescoreArm(HeadlineArm("b4_a50", "direction_4_neurologic_thin_b4_a50_hl50_B", "direction_4_smoke5_b4_a50.db", None, "beams=4 alpha=50")),
    RescoreArm(HeadlineArm("b8_a20", "direction_4_neurologic_thin_b8_a20_hl50_B", "direction_4_smoke5_b8_a20.db", None, "beams=8 alpha=20")),
    RescoreArm(HeadlineArm("b8_a100", "direction_4_neurologic_thin_b8_a100_hl50_B", "direction_4_smoke5_b8_a100.db", None, "beams=8 alpha=100")),
    RescoreArm(HeadlineArm("b16_a50", "direction_4_neurologic_thin_b16_a50_hl50_B", "direction_4_smoke5_b16_a50.db", None, "beams=16 alpha=50")),
    RescoreArm(HeadlineArm("b16_a100", "direction_4_neurologic_thin_b16_a100_hl50_B", "direction_4_smoke5_b16_a100.db", None, "beams=16 alpha=100")),
    RescoreArm(HeadlineArm("len_lam03", "direction_4_neurologic_thin_len_lam03_hl50_B", "direction_4_smoke5_len_lam03.db", None, "len + lambda=0.3")),
    RescoreArm(HeadlineArm("v2", "direction_4_neurologic_thin_v2_hl50_B", "direction_4_smoke5_v2.db", None, "combined v2")),
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
            "ref_soft_plain_B_beams8",
            "direction_1b_soft_plain_hl50_B_beams8",
            "direction_1p2_smoke5_soft_plain_B_beams8.db",
            1,
            "Soft beams8 reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_softneg_thin_B",
            "direction_1c_soft_morph_softneg_thin_hl50_B",
            "direction_3b_smoke5_softneg_thin_B.db",
            None,
            "Softneg thin reference",
        ),
        required=False,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore Direction 4 Neurologic ablation smoke5 DBs"
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("research/runs"))
    parser.add_argument("--evaluator", choices=EVALUATOR_CHOICES, default="both")
    parser.add_argument("--ppl-commit-every", type=int, default=200)
    parser.add_argument("--judge-commit-every", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--new-arms-only", action="store_true")
    args = parser.parse_args()

    arms = ABLATION_ARMS + (() if args.new_arms_only else REFERENCE_ARMS)
    print(
        f"Direction 4 Neurologic ablation rescore — {len(arms)} arms "
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
