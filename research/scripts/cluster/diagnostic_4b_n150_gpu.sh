#!/bin/bash
#SBATCH --job-name=d4b_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_4b_n150_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUTPUT_4B="${PROJECT}/docs/spike-results/eval_diagnostic_4b_n150_sentence_qwen_results.json"
D2A="${PROJECT}/docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json"
D3C="${PROJECT}/docs/spike-results/eval_diagnostic_3c_n150_sentence_qwen_results.json"

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
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
export HF_HOME="${PROJECT}/.cache/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Diagnostic 4B n=150 — $(date -Is) ==="
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

if [[ ! -f "${D2A}" ]]; then
  echo "WARNING: ${D2A} missing — binding-gap summary will be skipped." >&2
fi
if [[ ! -f "${D3C}" ]]; then
  echo "WARNING: ${D3C} missing — will run pass@1 inline (slower)." >&2
  REUSE_FLAG="--no-reuse-3c-pass1"
else
  echo "Reusing Diagnostic 3C pass@1 where available."
  REUSE_FLAG="--reuse-3c-pass1"
fi

run_model() {
  local model="$1"
  local batch
  case "${model}" in
    qwen4b) batch="${BATCH_JSON_4B}" ;;
    *) batch="${BATCH_JSON_17B}" ;;
  esac
  echo ""
  echo "=== ${model}: diagnostic_4b (self-correct) ==="
  python3 -m research.prototyping.diagnostic_4_spanish_prompt_ablation_qwen_spike \
    --variant diagnostic_4b \
    --models "${model}" \
    --output "${OUTPUT_4B}" \
    --d2a-results "${D2A}" \
    --d3c-results "${D3C}" \
    ${REUSE_FLAG} \
    --batch-size "${batch}" \
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

path = Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_4b_n150_sentence_qwen_results.json")
if not path.is_file():
    print(f"missing {path}")
else:
    d = json.loads(path.read_text())
    print("models", list(d.get("by_model", {})))
    print(json.dumps(d.get("summary", {}), indent=2)[:4000])
PY
