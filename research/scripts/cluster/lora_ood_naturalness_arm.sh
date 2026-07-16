#!/bin/bash
# Rescore PPL + LLM judge for a LoRA OOD DB.
#
# Required env:
#   DB_PATH       absolute path to per-arm sqlite DB
#   METHOD_NAME   method config name stored in the experiment (e.g. direction_2_lora_inject_ood_n36)
# Optional:
#   LABEL         log label (default: basename of DB)
#   EVALUATOR     both|perplexity|judge (default both)
#   RESUME        1|0 (default 1)
#
# Usage:
#   DB_PATH=... METHOD_NAME=... sbatch research/scripts/cluster/lora_ood_naturalness_arm.sh

#SBATCH --job-name=lora_ood_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_ood_natural_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
: "${DB_PATH:?Set DB_PATH}"
: "${METHOD_NAME:?Set METHOD_NAME}"
: "${LABEL:=$(basename "${DB_PATH}" .db)}"
: "${EVALUATOR:=both}"
: "${RESUME:=1}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

echo "=== LoRA OOD naturalness — $(date -Is) ==="
echo "  LABEL=${LABEL} METHOD=${METHOD_NAME}"
echo "  DB=${DB_PATH} EVALUATOR=${EVALUATOR} RESUME=${RESUME}"
nvidia-smi || true

export DB_PATH METHOD_NAME LABEL EVALUATOR RESUME
python3 - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from research.scripts.rescore_direction_1_naturalness import _run_one

_run_one(
    label=os.environ["LABEL"],
    method_name=os.environ["METHOD_NAME"],
    db_path=Path(os.environ["DB_PATH"]),
    experiment_id=None,
    which=os.environ.get("EVALUATOR", "both"),
    ppl_commit_every=200,
    judge_commit_every=50,
    resume=os.environ.get("RESUME", "1") != "0",
    dry_run=False,
)
print("=== naturalness done ===")
PY
