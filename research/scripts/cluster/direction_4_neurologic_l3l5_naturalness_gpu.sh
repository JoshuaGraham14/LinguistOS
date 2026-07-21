#!/bin/bash
# Naturalness (PPL + LLM judge) for Direction 4 L3/L5 spike DBs.
#
# Prefer submitting via direction_4_neurologic_l3l5_parallel_submit.sh so this
# waits on generation jobs.

#SBATCH --job-name=d4_l3l5_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_l3l5_nat_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"

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

echo "=== Direction 4 L3/L5 naturalness — $(date -Is) ==="
python3 -m research.scripts.rescore_neurologic_l3l5_naturalness --evaluator both --resume
echo "=== Direction 4 L3/L5 naturalness done $(date -Is) ==="
