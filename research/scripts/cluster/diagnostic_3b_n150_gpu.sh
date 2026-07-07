#!/bin/bash
#SBATCH --job-name=d3b_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_3b_n150_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUTPUT_3B="${PROJECT}/docs/spike-results/eval_diagnostic_3b_n150_sentence_qwen_results.json"
D2A="${PROJECT}/docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json"

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

echo "=== Diagnostic 3B n=150 — $(date -Is) ==="
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

if [[ ! -f "${D2A}" ]]; then
  echo "WARNING: ${D2A} missing — binding-gap summary will be skipped." >&2
fi

run_model() {
  local model="$1"
  echo ""
  echo "=== ${model}: diagnostic_3b (production baseline prompt) ==="
  python3 -m research.prototyping.diagnostic_3_spanish_sentence_qwen_spike \
    --variant diagnostic_3b \
    --models "${model}" \
    --output "${OUTPUT_3B}" \
    --d2a-results "${D2A}" \
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

path = Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_3b_n150_sentence_qwen_results.json")
if not path.is_file():
    print(f"missing {path}")
else:
    d = json.loads(path.read_text())
    print("models", list(d.get("by_model", {})))
    print(json.dumps(d.get("summary", {}), indent=2)[:4000])
PY
