#!/bin/bash
# Welsh Diagnostic 2A frontier ceiling — same prompts as Qwen 2A, model=gpt-5.5.
# API-bound (GPU mostly unused); a30 for queue availability.
#
# Usage (from LinguistOS-welsh):
#   sbatch research/scripts/cluster/welsh_diag2a_n10_gpt55.sh

#SBATCH --job-name=welsh_d2a_gpt55
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_diag2a_n10_gpt55_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
OUTPUT="${PROJECT}/research/welsh/manifests/eval_diagnostic_2a_welsh_n10_gpt55_results.json"
: "${RESUME:=1}"
: "${REASONING_EFFORT:=low}"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/welsh/manifests"

# Prefer MAIN .venv (has openai); welsh tree usually symlinks it.
if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "Missing venv" >&2
  exit 1
fi

python -c "import openai" || {
  echo "ERROR: openai not installed in active venv" >&2
  exit 1
}

cd "${PROJECT}"
export PROJECT
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
elif [[ -f "${MAIN}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MAIN}/research/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY not set" >&2
  exit 1
fi

echo "=== Welsh Diagnostic 2A GPT-5.5 n10 — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  OUTPUT=${OUTPUT}"
echo "  RESUME=${RESUME} REASONING_EFFORT=${REASONING_EFFORT}"

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

python3 -m research.prototyping.diagnostic_2_welsh_paradigm_qwen_spike \
  --models gpt55 \
  --output "${OUTPUT}" \
  --temperature 0 \
  --reasoning-effort "${REASONING_EFFORT}" \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Welsh Diagnostic 2A GPT-5.5 done $(date -Is) ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("research/welsh/manifests/eval_diagnostic_2a_welsh_n10_gpt55_results.json")
obj = json.loads(p.read_text())
s = obj["summary"]["per_model"]["gpt55"]
print("vs Qwen3-1.7B earlier: overall ~0.95% / syn 2.2% / peri 0%")
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
