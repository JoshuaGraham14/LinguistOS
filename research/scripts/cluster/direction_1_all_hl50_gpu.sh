#!/bin/bash
# Run all six core Direction 1 pilot arms SEQUENTIALLY on one GPU.
# Prefer three parallel jobs (inject / hard / soft) to finish ~3× faster:
#   sbatch research/scripts/cluster/direction_1_inject_hl50_gpu.sh
#   sbatch research/scripts/cluster/direction_1_hard_hl50_gpu.sh
#   sbatch research/scripts/cluster/direction_1_soft_hl50_gpu.sh
#
# Usage: sbatch research/scripts/cluster/direction_1_all_hl50_gpu.sh

#SBATCH --job-name=d1_all_hl50
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1_all_hl50_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50

METHODS=(
  direction_1_inject_json_hl50
  direction_1_inject_plain_hl50
  direction_1a_hard_plain_hl50
  direction_1a_hard_json_hl50
  direction_1b_soft_plain_hl50
  direction_1b_soft_json_hl50
)

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Create venv: python3 -m venv ${VENV} && pip install -r research/requirements.txt torch transformers accelerate" >&2
  exit 1
fi

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
fi

cd "${PROJECT}"
export HF_HOME="${PROJECT}/.cache/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Direction 1 pilot (6 core arms) — $(date -Is) ==="
nvidia-smi || true

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

for METHOD in "${METHODS[@]}"; do
  echo ""
  echo "=== ${METHOD} — $(date -Is) ==="
  python3 -m research.run_experiment \
    --benchmark "${BENCHMARK}" \
    --method "${METHOD}" \
    --live \
    --resume
done

echo ""
echo "=== All core arms done $(date -Is) ==="
