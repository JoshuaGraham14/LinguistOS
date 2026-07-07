#!/bin/bash
#SBATCH --job-name=d2_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_2_n150_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUTPUT_PARADIGM="${PROJECT}/docs/spike-results/eval_diagnostic_2_n150_paradigm_qwen_results.json"
OUTPUT_SINGLE="${PROJECT}/docs/spike-results/eval_diagnostic_2_n150_single_slot_qwen_results.json"

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

echo "=== Diagnostic 2 n=150 — $(date -Is) ==="
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

run_model() {
  local model="$1"
  echo ""
  echo "=== ${model}: full_paradigm ==="
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
    --probe-mode full_paradigm \
    --models "${model}" \
    --output "${OUTPUT_PARADIGM}" \
    --resume

  echo ""
  echo "=== ${model}: single_slot ==="
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
    --probe-mode single_slot \
    --models "${model}" \
    --output "${OUTPUT_SINGLE}" \
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

for label, path in [
    ("paradigm", Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_2_n150_paradigm_qwen_results.json")),
    ("single_slot", Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_2_n150_single_slot_qwen_results.json")),
]:
    if not path.is_file():
        print(f"{label}: missing {path}")
        continue
    d = json.loads(path.read_text())
    print(f"\n{label}: models", list(d.get("by_model", {})))
    print(json.dumps(d.get("summary", {}), indent=2)[:2000])
PY
