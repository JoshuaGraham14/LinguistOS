#!/bin/bash
# Welsh transfer smoke — vanilla vs form-inject on Qwen3-1.7B.
#
# Tiny syn+peri cell set from research/benchmarks/welsh_smoke.yaml
# (built from welsh_cases_n150.csv). Runs on cluster GPU like Spanish smokes.
#
# Usage:
#   sbatch research/scripts/cluster/welsh_smoke_gpu.sh

#SBATCH --job-name=welsh_smoke
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/welsh_smoke_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUT="${PROJECT}/research/welsh/manifests/welsh_smoke_results.json"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/welsh/manifests"

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
if [[ -f "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
fi
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

echo "=== Welsh smoke (vanilla + inject, Qwen3-1.7B) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

python3 -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"

python3 -m research.benchmarks.loader research/benchmarks/welsh_smoke.yaml

python3 -m research.prototyping.welsh_form_injection_qwen_smoke \
  --benchmark welsh_smoke \
  --model qwen17b \
  --samples 1 \
  --conditions vanilla inject \
  --out "${OUT}"

echo ""
echo "=== Welsh smoke done $(date -Is) ==="
echo "Results: ${OUT}"
