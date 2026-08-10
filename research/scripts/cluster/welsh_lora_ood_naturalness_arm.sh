#!/bin/bash
# Rescore PPL + Welsh LLM judge for a Welsh LoRA OOD DB.
#
# Required env:
#   DB_PATH       absolute path to per-arm sqlite DB
#   METHOD_NAME   method config name stored in the experiment
# Optional:
#   LABEL         log label (default: basename of DB)
#   EVALUATOR     both|perplexity|judge (default both)
#   RESUME        1|0 (default 1)

#SBATCH --job-name=cy_lora_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_lora_ood_nat_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
: "${DB_PATH:?Set DB_PATH}"
: "${METHOD_NAME:?Set METHOD_NAME}"
: "${LABEL:=$(basename "${DB_PATH}" .db)}"
: "${EVALUATOR:=both}"
: "${RESUME:=1}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "ERROR: no usable venv" >&2
  exit 1
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
elif [[ -f "${MAIN}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MAIN}/research/.env"
  set +a
fi

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

echo "=== Welsh LoRA OOD naturalness — $(date -Is) ==="
echo "  LABEL=${LABEL} METHOD=${METHOD_NAME}"
echo "  DB=${DB_PATH} EVALUATOR=${EVALUATOR} RESUME=${RESUME}"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION; print('welsh_prompt', WELSH_PROMPT_VERSION)"
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
