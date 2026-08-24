#!/bin/bash
# Welsh LoRA OOD n36 — thin Neurologic arm (base or adapter via LORA_ADAPTER_PATH).
#
# Env:
#   ARM = vanilla | inject
#   LORA_ADAPTER_PATH = optional peft adapter (omit for base)
#   RESEARCH_DB = output db path
#
# Usage:
#   ARM=vanilla RESEARCH_DB=.../welsh_lora_ood_neuro_vanilla_base.db \
#     sbatch research/welsh/scripts/cluster/welsh_lora_neuro_ood_eval_arm.sh

#SBATCH --job-name=cy_neuro_ood
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=48:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_lora_ood_neuro_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
: "${ARM:?Set ARM=vanilla|inject}"
: "${RESEARCH_DB:?Set RESEARCH_DB path}"

case "${ARM}" in
  vanilla) METHOD=welsh_lora_neuro_vanilla_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}" ;;
  inject) METHOD=welsh_lora_neuro_inject_ood_n36; HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}" ;;
  *) echo "Unknown ARM=${ARM}" >&2; exit 1 ;;
esac

if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "ERROR: no usable venv" >&2
  exit 1
fi

cd "${PROJECT}"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
if [[ -f "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
fi
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export HF_BATCH_SIZE
export RESEARCH_DB

if [[ -n "${LORA_ADAPTER_PATH:-}" ]]; then
  export LORA_ADAPTER_PATH
  echo "Using LoRA adapter: ${LORA_ADAPTER_PATH}"
  python3 - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("peft") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "peft"])
PY
fi

mkdir -p "$(dirname "${RESEARCH_DB}")" "${PROJECT}/logs"

if [[ ! -f "${PROJECT}/research/benchmarks/welsh_transfer_ood_n36.yaml" ]]; then
  echo "ERROR: missing welsh_transfer_ood_n36.yaml under ${PROJECT}" >&2
  exit 1
fi

echo "=== Welsh LoRA OOD Neurologic gen — $(date -Is) ==="
echo "  ARM=${ARM} METHOD=${METHOD} DB=${RESEARCH_DB}"
echo "  LORA_ADAPTER_PATH=${LORA_ADAPTER_PATH:-<base>}"
python3 -c "from research.generation import GENERATOR_REGISTRY; print('neuro_plain', 'welsh_neurologic_hf_thin_plain_b' in GENERATOR_REGISTRY); print('neuro_inject', 'welsh_neurologic_hf_thin_inject_plain_b' in GENERATOR_REGISTRY)"
python3 -c "from research.welsh.morph_bans import build_welsh_morph_ban_set; print('welsh_morph_bans: ok')"

python3 -m research.run_experiment \
  --benchmark welsh_transfer_ood_n36 \
  --method "${METHOD}" \
  --live \
  --skip-experiment-group-metrics

echo "Done → ${RESEARCH_DB}"
