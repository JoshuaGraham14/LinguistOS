#!/bin/bash
# Frontier ceiling: GPT-5.5 Fix-B plain vanilla on spanish_lora_ood_n36.
# Phase A — generation + EF / length / LT (API-bound; GPU unused but required
# by Slurm partitions). Prefer partition=t4 to avoid a30 QOS contention.
#
# Writes ONLY to RESEARCH_DB (default under research/runs/).
#
# Usage:
#   sbatch research/scripts/cluster/frontier_ceiling_gpt55_ood_gen.sh
#   RESEARCH_DB=.../custom.db sbatch ...

#SBATCH --job-name=gpt55_ood_gen
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=t4
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55/logs/frontier_ceiling_gpt55_ood_gen_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

METHOD=frontier_ceiling_gpt55_vanilla_ood_n36
BENCHMARK=spanish_lora_ood_n36
RESEARCH_DB="${RESEARCH_DB:-${PROJECT}/research/runs/frontier_ceiling_gpt55_vanilla_ood_n36.db}"

mkdir -p "$(dirname "${RESEARCH_DB}")" "${PROJECT}/logs"

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

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export RESEARCH_DB

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

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY not set (expected in research/.env)" >&2
  exit 1
fi

echo "=== Frontier ceiling GPT-5.5 OOD gen — $(date -Is) ==="
echo "  PROJECT=${PROJECT}"
echo "  METHOD=${METHOD} BENCHMARK=${BENCHMARK}"
echo "  RESEARCH_DB=${RESEARCH_DB}"
echo "  HOST=$(hostname) CUDA=${CUDA_VISIBLE_DEVICES:-unset}"

python -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume \
  --skip-experiment-group-metrics

echo "Done → ${RESEARCH_DB}"
