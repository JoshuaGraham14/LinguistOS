#!/bin/bash
#SBATCH --job-name=d5c_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_5c_n150_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_diagnostic_n150
METHOD=diagnostic_5c_hf_qwen3_17b_n10
RUNS_DIR="${PROJECT}/research/runs"

mkdir -p "${PROJECT}/logs" "${PROJECT}/docs/spike-results" "${RUNS_DIR}"

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
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export RESEARCH_DB="${RUNS_DIR}/diagnostic_5c.db"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Diagnostic 5C n=150 (inject+explicit, T=0.7, n=10) — $(date -Is) ==="
echo "RESEARCH_DB=${RESEARCH_DB}"
echo "LTP_PATH=${LTP_PATH}"
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume \
  --skip-experiment-group-metrics

echo ""
echo "=== Done $(date -Is) ==="
