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
OUTPUT_2A="${PROJECT}/docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json"
OUTPUT_2B="${PROJECT}/docs/spike-results/eval_diagnostic_2b_n150_single_slot_qwen_results.json"

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

echo "=== Diagnostic 2 (2A + 2B) n=150 — $(date -Is) ==="
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

run_model() {
  local model="$1"
  local batch_2a batch_2b
  case "${model}" in
    qwen4b)
      batch_2a="${BATCH_MEDIUM_4B}"
      batch_2b="${BATCH_SHORT_4B}"
      ;;
    *)
      batch_2a="${BATCH_MEDIUM_17B}"
      batch_2b="${BATCH_SHORT_17B}"
      ;;
  esac
  echo ""
  echo "=== ${model}: diagnostic_2a (full paradigm, batch=${batch_2a}) ==="
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
    --probe-mode diagnostic_2a \
    --models "${model}" \
    --output "${OUTPUT_2A}" \
    --batch-size "${batch_2a}" \
    --resume

  echo ""
  echo "=== ${model}: diagnostic_2b (single slot, batch=${batch_2b}) ==="
  python3 -m research.prototyping.diagnostic_2_spanish_paradigm_qwen_spike \
    --probe-mode diagnostic_2b \
    --models "${model}" \
    --output "${OUTPUT_2B}" \
    --batch-size "${batch_2b}" \
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
    ("2A", Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_2a_n150_paradigm_qwen_results.json")),
    ("2B", Path("/vol/bitbucket/jjg25/LinguistOS/docs/spike-results/eval_diagnostic_2b_n150_single_slot_qwen_results.json")),
]:
    if not path.is_file():
        print(f"{label}: missing {path}")
        continue
    d = json.loads(path.read_text())
    print(f"\n{label}: models", list(d.get("by_model", {})))
    print(json.dumps(d.get("summary", {}), indent=2)[:2000])
PY
