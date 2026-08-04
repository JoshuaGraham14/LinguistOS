#!/bin/bash
# Welsh Diagnostic 2A n10 — Qwen3-4B arm (wraps welsh_diag2a_n10_gpu.sh).
#
# Usage (from LinguistOS-welsh tree):
#   sbatch research/scripts/cluster/welsh_diag2a_n10_qwen4b.sh

#SBATCH --job-name=welsh_d2a_4b
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_diag2a_n10_qwen4b_%j.out

set -euo pipefail

export MODEL=qwen4b
export RESUME="${RESUME:-1}"

# Re-exec the shared body without nested #SBATCH (source after stripping headers is brittle);
# inline the shared runner by calling the python path directly with 4B defaults.
PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
OUTPUT="${PROJECT}/research/welsh/manifests/eval_diagnostic_2a_welsh_n10_qwen4b_results.json"

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
export HF_HOME="${MAIN}/.cache/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}"
if [[ -f "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
fi
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

BATCH_SIZE="${BATCH_MEDIUM_4B:-8}"

echo "=== Welsh Diagnostic 2A n10 Qwen3-4B — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  MODEL=qwen4b BATCH_SIZE=${BATCH_SIZE} RESUME=${RESUME}"
echo "  OUTPUT=${OUTPUT}"
nvidia-smi || true
python3 -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike \
  --models qwen4b \
  --output "${OUTPUT}" \
  --batch-size "${BATCH_SIZE}" \
  --temperature 0 \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Welsh Diagnostic 2A Qwen3-4B done $(date -Is) ==="
echo "Results: ${OUTPUT}"
python3 - <<'PY'
import json
from pathlib import Path

p = Path("research/welsh/manifests/eval_diagnostic_2a_welsh_n10_qwen4b_results.json")
obj = json.loads(p.read_text())
print(f"  scoring_version={obj.get('scoring_version')}")
s = obj["summary"]["per_model"]["qwen4b"]
for k in (
    "overall_strict",
    "overall_perfect_paradigm",
    "synthetic_strict",
    "synthetic_perfect",
    "periphrastic_strict",
    "periphrastic_perfect",
    "periphrastic_aux_recall",
    "periphrastic_vn_recall",
):
    print(f"  {k}: {s.get(k)}")
PY
