#!/bin/bash
# Generation-only cost calibration on spanish_cost_cal_n36_3verb (93 cells).
#
# Env:
#   COST_ARM_LABEL  short arm id (e.g. base17_vanilla)
#   METHOD_NAME     method YAML name
#   RESEARCH_DB     per-arm sqlite path
#   RESEARCH_COST_LOG  JSON output path
#   LORA_ADAPTER_PATH  optional
#   HF_BATCH_SIZE      optional override
#
# Usage:
#   COST_ARM_LABEL=base17_vanilla METHOD_NAME=direction_1_vanilla_plain_n150_B \
#     RESEARCH_DB=... RESEARCH_COST_LOG=... \
#     sbatch research/scripts/cluster/cost_cal_arm.sh

#SBATCH --job-name=cost_cal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=03:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/cost_cal_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

: "${COST_ARM_LABEL:?Set COST_ARM_LABEL}"
: "${METHOD_NAME:?Set METHOD_NAME}"
: "${RESEARCH_DB:?Set RESEARCH_DB}"
: "${RESEARCH_COST_LOG:?Set RESEARCH_COST_LOG}"

# Default batch sizes match prior n150 / LoRA OOD practice.
# NeuroLogic OOD arms use beam 16 and were timed/evaluated at batch 1.
case "${METHOD_NAME}" in
  *neuro*|*neurologic*) HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}" ;;
  *soft*|*hard*|direction_1a_*) HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}" ;;
  *) HF_BATCH_SIZE="${HF_BATCH_SIZE:-16}" ;;
esac

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "No venv found" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
export PYTHONUNBUFFERED=1
export HF_BATCH_SIZE
export COST_ARM_LABEL
export RESEARCH_DB
export RESEARCH_COST_LOG

if [[ -n "${LORA_ADAPTER_PATH:-}" ]]; then
  export LORA_ADAPTER_PATH
  echo "Using LoRA adapter: ${LORA_ADAPTER_PATH}"
  python - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("peft") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "peft"])
PY
fi

mkdir -p "$(dirname "${RESEARCH_DB}")" "$(dirname "${RESEARCH_COST_LOG}")" "${PROJECT}/logs"

echo "COST_ARM_LABEL=${COST_ARM_LABEL}"
echo "METHOD_NAME=${METHOD_NAME}"
echo "RESEARCH_DB=${RESEARCH_DB}"
echo "RESEARCH_COST_LOG=${RESEARCH_COST_LOG}"
echo "HF_BATCH_SIZE=${HF_BATCH_SIZE}"
echo "LORA_ADAPTER_PATH=${LORA_ADAPTER_PATH:-}"

python -m research.run_experiment \
  --benchmark spanish_cost_cal_n36_3verb \
  --method "${METHOD_NAME}" \
  --live \
  --no-eval \
  --no-metrics

echo "Done → db=${RESEARCH_DB} cost=${RESEARCH_COST_LOG}"
if [[ -f "${RESEARCH_COST_LOG}" ]]; then
  python - <<PY
import json
p = "${RESEARCH_COST_LOG}"
print(json.dumps(json.load(open(p)), indent=2))
PY
fi
