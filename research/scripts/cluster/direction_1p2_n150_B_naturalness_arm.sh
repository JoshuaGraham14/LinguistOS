#!/bin/bash
# One-arm naturalness rescore for Direction 1.2 Fix-B n150.
# Required env: ARM (e.g. inject_plain_B)
# Optional: EVALUATOR=both|perplexity|judge  RESUME=0|1
#
# Usually submitted via direction_1p2_n150_B_naturalness_parallel_submit.sh

#SBATCH --job-name=d1n150_nat1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_n150_natural_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
: "${ARM:?Set ARM}"
: "${EVALUATOR:=both}"
: "${RESUME:=1}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv" >&2
  exit 1
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

echo "=== D1.2 n150 naturalness ONE-ARM — $(date -Is) ==="
echo "  ARM=${ARM}  EVALUATOR=${EVALUATOR}  RESUME=${RESUME}"
nvidia-smi || true

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

export ARM EVALUATOR RESUME
python3 - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from research.scripts.rescore_direction_1_naturalness import (
    HEADLINE_N150_B_ARMS,
    HeadlineArm,
    _run_one,
)

arm_key = os.environ["ARM"]
evaluator = os.environ.get("EVALUATOR", "both")
resume = os.environ.get("RESUME", "1") != "0"
runs = Path("research/runs")

extras = [
    HeadlineArm(
        key="soft_plain_B_beams8_qwen4b",
        method_name="direction_1b_soft_plain_n150_B_beams8_qwen4b",
        db_name="direction_1p2_n150_soft_plain_B_beams8_qwen4b.db",
        experiment_id=None,
        note="Soft + Fix B beams8 on Qwen3-4B",
    ),
    HeadlineArm(
        key="vanilla_plain_B_qwen4b",
        method_name="direction_1_vanilla_plain_n150_B_qwen4b",
        db_name="direction_1p2_n150_vanilla_plain_B_qwen4b.db",
        experiment_id=None,
        note="Vanilla Fix B control on Qwen3-4B",
    ),
    HeadlineArm(
        key="hard_plain_B_qwen4b",
        method_name="direction_1a_hard_plain_n150_B_qwen4b",
        db_name="direction_1p2_n150_hard_plain_B_qwen4b.db",
        experiment_id=None,
        note="Hard force + Fix B on Qwen3-4B",
    ),
]
lookup = {a.key: a for a in list(HEADLINE_N150_B_ARMS) + extras}
arm = lookup.get(arm_key)
if arm is None:
    raise SystemExit(f"Unknown ARM={arm_key!r}. Known: {sorted(lookup)}")

db = runs / arm.db_name
if not db.is_file():
    raise SystemExit(f"Missing DB: {db}")

_run_one(
    label=arm.key,
    method_name=arm.method_name,
    db_path=db,
    experiment_id=arm.experiment_id,
    which=evaluator,
    ppl_commit_every=200,
    judge_commit_every=50,
    resume=resume,
    dry_run=False,
    note=arm.note,
)
print(f"Done arm={arm.key}", flush=True)
PY

echo "=== one-arm ${ARM} done $(date -Is) ==="
