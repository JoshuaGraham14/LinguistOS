#!/bin/bash
# Direction 4 PPL + LLM-judge rescore. Submit with afterok on generation.
#
# Usage:
#   sbatch --dependency=afterok:<GEN_JOB_ID> \
#     research/scripts/cluster/direction_4_neurologic_naturalness_gpu.sh

#SBATCH --job-name=d4_neuro_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_neurologic_natural_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
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
  echo "Missing venv at ${VENV}" >&2
  exit 1
fi

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
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

echo "=== Direction 4 Neurologic naturalness rescore — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR}  RESUME=${RESUME}"
nvidia-smi || true

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
  fi
fi

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

python3 -m research.scripts.rescore_neurologic_naturalness \
  --evaluator "${EVALUATOR}" \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Direction 4 naturalness rescore done $(date -Is) ==="
