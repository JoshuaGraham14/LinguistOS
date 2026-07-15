#!/bin/bash
# Naturalness rescore for completed Direction 1.2 Fix-B n150 arms.
# Runs fluency_perplexity (GPU) + naturalness_llm_judge (OpenAI).
#
# By default only arms whose experiment status is ``completed`` are scored,
# so this can start while hard / qwen4b are still generating.
#
# Usage:
#   sbatch research/scripts/cluster/direction_1p2_n150_B_naturalness_rescore.sh
#   ARMS="vanilla_plain_B inject_plain_B" sbatch ...   # optional subset
#   EVALUATOR=perplexity sbatch ...

#SBATCH --job-name=d1n150_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_n150_natural_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
: "${EVALUATOR:=both}"
: "${RESUME:=1}"
# Optional space-separated arm keys; empty = all completed HEADLINE_N150_B arms
: "${ARMS:=}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv at ${VENV}" >&2
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

echo "=== D1.2 Fix-B n150 naturalness rescore — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR}  RESUME=${RESUME}  ARMS=${ARMS:-<auto completed>}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.fluency_perplexity import FluencyPerplexityEvaluator
from research.evaluation.sentence.naturalness_llm_judge import NaturalnessLlmJudgeEvaluator
print(f"OK: {FluencyPerplexityEvaluator().name} + {NaturalnessLlmJudgeEvaluator().name}")
PY

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG=(--resume)
fi

export EVALUATOR
export ARMS
export RESUME

python3 - <<'PY'
"""Rescore only completed (or explicitly requested) n150 Fix-B arms."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from research.scripts.rescore_direction_1_naturalness import (
    HEADLINE_N150_B_ARMS,
    _run_one,
)

runs = Path("research/runs")
evaluator = os.environ.get("EVALUATOR", "both")
resume = os.environ.get("RESUME", "1") != "0"
requested = [a for a in os.environ.get("ARMS", "").split() if a]

arms = list(HEADLINE_N150_B_ARMS)
# Optional 4B probe — include when its DB exists / completed
from research.scripts.rescore_direction_1_naturalness import HeadlineArm

arms_extra = (
    HeadlineArm(
        key="soft_plain_B_beams8_qwen4b",
        method_name="direction_1b_soft_plain_n150_B_beams8_qwen4b",
        db_name="direction_1p2_n150_soft_plain_B_beams8_qwen4b.db",
        experiment_id=None,
        note="Soft + Fix B beams8 on Qwen3-4B",
    ),
)
all_arms = tuple(arms) + arms_extra

if requested:
    selected = [a for a in all_arms if a.key in set(requested)]
    missing = set(requested) - {a.key for a in selected}
    if missing:
        raise SystemExit(f"Unknown ARMS: {sorted(missing)}")
else:
    selected = []
    for arm in all_arms:
        db = runs / arm.db_name
        if not db.is_file():
            print(f"Skip {arm.key}: DB missing", flush=True)
            continue
        con = sqlite3.connect(db)
        row = con.execute(
            "select status from experiments where name like ? order by id limit 1",
            (f"%{arm.method_name}%",),
        ).fetchone()
        con.close()
        status = row[0] if row else None
        if status != "completed":
            print(f"Skip {arm.key}: status={status!r} (need completed)", flush=True)
            continue
        selected.append(arm)

print(
    f"Rescoring {len(selected)} arm(s): "
    + ", ".join(a.key for a in selected),
    flush=True,
)
if not selected:
    raise SystemExit("No completed arms to rescore")

for arm in selected:
    _run_one(
        label=arm.key,
        method_name=arm.method_name,
        db_path=runs / arm.db_name,
        experiment_id=arm.experiment_id,
        which=evaluator,
        ppl_commit_every=200,
        judge_commit_every=50,
        resume=resume,
        dry_run=False,
        note=arm.note,
    )

print("All selected arms rescored.", flush=True)
PY

echo ""
echo "=== n150 naturalness rescore done $(date -Is) ==="
