#!/usr/bin/env python3
"""PPL + LLM-judge rescore for Direction 3 morphology-aware smoke5 arms.

This is intentionally a separate entry point: the locked Direction 1/1.2
rescore presets and CLI remain unchanged.
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


MORPH_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "morph_ban_B",
            "direction_1c_morph_ban_hl50_B",
            "direction_3_smoke5_morph_ban_B.db",
            None,
            "Full morphology bans only",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "morph_ban_inject_B",
            "direction_1c_morph_ban_inject_hl50_B",
            "direction_3_smoke5_morph_ban_inject_B.db",
            None,
            "Full bans + prompt injection",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "hard_morph_B",
            "direction_1c_hard_morph_hl50_B",
            "direction_3_smoke5_hard_morph_B.db",
            None,
            "Hard force + full bans",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "hard_morph_inject_B",
            "direction_1c_hard_morph_inject_hl50_B",
            "direction_3_smoke5_hard_morph_inject_B.db",
            None,
            "Hard force + full bans + injection",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "soft_morph_B",
            "direction_1c_soft_morph_hl50_B",
            "direction_3_smoke5_soft_morph_B.db",
            None,
            "Soft λ=5 + full bans",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "soft_morph_inject_B",
            "direction_1c_soft_morph_inject_hl50_B",
            "direction_3_smoke5_soft_morph_inject_B.db",
            None,
            "Soft λ=5 + full bans + injection",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "soft_morph_forms_B",
            "direction_1c_soft_morph_forms_hl50_B",
            "direction_3_smoke5_soft_morph_forms_B.db",
            None,
            "Soft λ=5 + form/infinitive bans only",
        )
    ),
    RescoreArm(
        HeadlineArm(
            "soft_morph_pron_B",
            "direction_1c_soft_morph_pron_hl50_B",
            "direction_3_smoke5_soft_morph_pron_B.db",
            None,
            "Soft λ=5 + pronoun bans only",
        )
    ),
)

# Contextual DBs are useful when present, but their absence must not prevent
# the eight new arms from completing overnight.
REFERENCE_ARMS: tuple[RescoreArm, ...] = (
    RescoreArm(
        HeadlineArm(
            "ref_soft_plain_B_beams8",
            "direction_1b_soft_plain_hl50_B_beams8",
            "direction_1p2_smoke5_soft_plain_B_beams8.db",
            1,
            "Primary matched Direction 1.2 reference",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_vanilla_plain_B",
            "direction_1_vanilla_plain_hl50_B",
            "direction_1p2_smoke5_vanilla_plain_B.db",
            1,
            "Greedy Fix-B context",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_inject_plain",
            "direction_1_inject_plain_hl50",
            "direction_1p2_smoke5_inject_plain.db",
            1,
            "Prompt-injection context",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_soft_inject_plain_B",
            "direction_1b_soft_inject_plain_hl50_B",
            "direction_1p2_smoke5_soft_inject_plain_B.db",
            1,
            "Soft + inject + Fix-B context",
        ),
        required=False,
    ),
    RescoreArm(
        HeadlineArm(
            "ref_hard_plain_B",
            "direction_1a_hard_plain_hl50_B",
            "direction_1p2_smoke5_hard_plain_B.db",
            1,
            "Hard + Fix-B context",
        ),
        required=False,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore Direction 3 smoke5 DBs with PPL and/or LLM judge"
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
        help="Skip pre-existing Direction 1.2 reference DBs",
    )
    args = parser.parse_args()

    arms = MORPH_ARMS + (() if args.new_arms_only else REFERENCE_ARMS)
    print(
        f"Direction 3 morph-aware rescore — {len(arms)} arms "
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
