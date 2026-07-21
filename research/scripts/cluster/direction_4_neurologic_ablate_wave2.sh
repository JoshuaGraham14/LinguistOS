#!/bin/bash
# Wave 2: remaining Neurologic ablation arms (sequential on one GPU) + naturalness.
#
# Used when the parallel submitter hits QOSMaxSubmitJobPerUserLimit and only a
# subset of arms were queued. Prefer the parallel submit wrapper for fresh runs;
# this script is the catch-up path.
#
# Usage (usually via sbatch --dependency=afterany:id1:id2:...):
#   sbatch research/scripts/cluster/direction_4_neurologic_ablate_wave2.sh
#
# Optional env:
#   WAVE2_ARMS — space-separated arm keys (default: b16_a100 len_lam03 v2)

#SBATCH --job-name=d4_wave2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_ablate_wave2_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
cd "${PROJECT}"

if [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv at ${PROJECT}/.venv" >&2
  exit 1
fi

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
fi

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

ARM_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_ablate_arm_gpu.sh"
# shellcheck disable=SC2206
ARMS=(${WAVE2_ARMS:-b16_a100 len_lam03 v2})

for ARM in "${ARMS[@]}"; do
  export ARM
  echo "=== WAVE2 starting ARM=${ARM} $(date -Is) ==="
  bash "${ARM_SCRIPT}"
  echo "=== WAVE2 finished ARM=${ARM} $(date -Is) ==="
done

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

echo "=== WAVE2 naturalness $(date -Is) ==="
python3 -m research.scripts.rescore_neurologic_ablate_naturalness --evaluator both --resume
echo "=== WAVE2 done $(date -Is) ==="
