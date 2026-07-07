#!/bin/bash
#SBATCH --job-name=d1a_n25
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_1_n25_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUTPUT="${PROJECT}/docs/spike-results/eval_diagnostic_1_n25_isolation_qwen_results.json"

mkdir -p "${PROJECT}/logs" "${PROJECT}/docs/spike-results"

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

echo "=== Diagnostic 1A n=25 — $(date -Is) ==="
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

# Small/mid on a16-class VRAM; 4B gets its own process + --resume (24 GB A30).
run_model() {
  local model="$1"
  echo ""
  echo "=== Running ${model} ==="
  python3 -m research.prototyping.diagnostic_1_freq_validated_isolation_qwen_spike \
    --models "${model}" \
    --output "${OUTPUT}" \
    --resume
}

run_model qwen06b
run_model qwen17b
run_model qwen4b

echo ""
echo "=== Done $(date -Is) ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_1_n25_isolation_qwen_results.json")
d = json.loads(p.read_text())
print("Models in output:", list(d.get("by_model", {})))
print(json.dumps(d.get("summary", {}), indent=2)[:3000])
PY
