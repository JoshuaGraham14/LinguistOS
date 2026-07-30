#!/bin/bash
# Phase B — PPL + LLM judge rescore for frontier ceiling GPT-5.5 OOD DB.
# Prefer a30 when free; may sit behind other jobs under QOS.
#
# Usage:
#   DB_PATH=.../frontier_ceiling_gpt55_vanilla_ood_n36.db \
#     sbatch research/scripts/cluster/frontier_ceiling_gpt55_ood_nat.sh

#SBATCH --job-name=gpt55_ood_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55/logs/frontier_ceiling_gpt55_ood_nat_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55
VENV="${PROJECT}/.venv"
METHOD_NAME=frontier_ceiling_gpt55_vanilla_ood_n36
DB_PATH="${DB_PATH:-${PROJECT}/research/runs/frontier_ceiling_gpt55_vanilla_ood_n36.db}"
LABEL="${LABEL:-$(basename "${DB_PATH}" .db)}"
EVALUATOR="${EVALUATOR:-both}"
RESUME="${RESUME:-1}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/LinguistOS/research/.venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/LinguistOS/research/.venv/bin/activate
elif [[ -f /vol/bitbucket/jjg25/LinguistOS/.venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/LinguistOS/.venv/bin/activate
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# Reuse main checkout HF / LT caches so Salamandra is not re-downloaded.
MAIN_CACHE=/vol/bitbucket/jjg25/LinguistOS/.cache
if [[ -d "${MAIN_CACHE}/huggingface" ]]; then
  export HF_HOME="${MAIN_CACHE}/huggingface"
  export TRANSFORMERS_CACHE="${HF_HOME}"
fi
if [[ -d "${MAIN_CACHE}/language_tool_python" ]]; then
  export LTP_PATH="${MAIN_CACHE}/language_tool_python"
fi
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
elif [[ -f /vol/bitbucket/jjg25/LinguistOS/research/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/LinguistOS/research/.env
  set +a
fi

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

if [[ ! -f "${DB_PATH}" ]]; then
  echo "ERROR: DB not found: ${DB_PATH}" >&2
  exit 1
fi

echo "=== Frontier ceiling GPT-5.5 OOD naturalness — $(date -Is) ==="
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

echo "Done naturalness → ${DB_PATH}"
