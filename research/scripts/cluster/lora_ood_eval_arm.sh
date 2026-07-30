#!/bin/bash
# OOD n36 eval for base or LoRA-adapted Qwen3-1.7B (Fix-B decode arms).
#
# Env:
#   ARM = inject | vanilla | soft | soft_inject | neuro | neuro_inject
#   LORA_ADAPTER_PATH = optional path to peft adapter (omit for base)
#   RESEARCH_DB = output db path
#
# Usage:
#   ARM=inject RESEARCH_DB=research/runs/lora_ood_inject_base.db \
#     sbatch research/scripts/cluster/lora_ood_eval_arm.sh

#SBATCH --job-name=lora_ood
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_ood_eval_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

: "${ARM:?Set ARM=inject|vanilla|soft|soft_inject|neuro|neuro_inject}"
: "${RESEARCH_DB:?Set RESEARCH_DB path}"

case "${ARM}" in
  inject) METHOD=direction_2_lora_inject_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-16}" ;;
  vanilla) METHOD=direction_2_lora_vanilla_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-16}" ;;
  soft) METHOD=direction_2_lora_soft_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}" ;;
  soft_inject) METHOD=direction_2_lora_soft_inject_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}" ;;
  neuro) METHOD=direction_2_lora_neuro_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}" ;;
  neuro_inject) METHOD=direction_2_lora_neuro_inject_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}" ;;
  *) echo "Unknown ARM=${ARM}" >&2; exit 1 ;;
esac

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
fi

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
export PYTHONUNBUFFERED=1
export HF_BATCH_SIZE
if [[ -n "${LORA_ADAPTER_PATH:-}" ]]; then
  export LORA_ADAPTER_PATH
  echo "Using LoRA adapter: ${LORA_ADAPTER_PATH}"
  python - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("peft") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "peft"])
PY
fi

mkdir -p "$(dirname "${RESEARCH_DB}")" "${PROJECT}/logs"
export RESEARCH_DB

echo "ARM=${ARM} METHOD=${METHOD} DB=${RESEARCH_DB}"
python -m research.run_experiment \
  --benchmark spanish_lora_ood_n36 \
  --method "${METHOD}" \
  --live \
  --skip-experiment-group-metrics

echo "Done → ${RESEARCH_DB}"
