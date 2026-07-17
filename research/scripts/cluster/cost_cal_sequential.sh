#!/bin/bash
# Controlled cost calibration: all 15 arms sequentially on one allocated A30.
#
# Fairness controls:
#   - same GPU/node (single Slurm allocation)
#   - same 93-cell benchmark
#   - identical HF_BATCH_SIZE=4
#   - one untimed warm-up batch per arm/process
#   - three repeats; scoring disabled
#   - prompt and generated token telemetry
#
# Usage:
#   sbatch research/scripts/cluster/cost_cal_sequential.sh

#SBATCH --job-name=cost_seq15
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/cost_cal_sequential_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
ARM_SCRIPT="${PROJECT}/research/scripts/cluster/cost_cal_arm.sh"
OUT="${PROJECT}/research/runs/cost_cal_sequential"
LORA_A="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"
LORA_B="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_no_inject"

cd "${PROJECT}"
mkdir -p "${OUT}" "${PROJECT}/logs"

for adapter in "${LORA_A}" "${LORA_B}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    exit 1
  fi
done

# label|method|adapter (adapter may be empty)
ARMS=(
  "base17_vanilla|direction_1_vanilla_plain_n150_B|"
  "base17_inject|direction_1_inject_plain_n150_B|"
  "base17_soft4|direction_1b_soft_plain_n150_B|"
  "base17_soft8|direction_1b_soft_plain_n150_B_beams8|"
  "base17_soft_inject|direction_1b_soft_inject_plain_n150_B|"
  "base17_hard|direction_1a_hard_plain_n150_B|"
  "loraA_vanilla|direction_1_vanilla_plain_n150_B|${LORA_A}"
  "loraA_inject|direction_1_inject_plain_n150_B|${LORA_A}"
  "loraA_soft8|direction_1b_soft_plain_n150_B_beams8|${LORA_A}"
  "loraB_vanilla|direction_1_vanilla_plain_n150_B|${LORA_B}"
  "loraB_inject|direction_1_inject_plain_n150_B|${LORA_B}"
  "loraB_soft8|direction_1b_soft_plain_n150_B_beams8|${LORA_B}"
  "base4_vanilla|direction_1_vanilla_plain_n150_B_qwen4b|"
  "base4_soft8|direction_1b_soft_plain_n150_B_beams8_qwen4b|"
  "base4_hard|direction_1a_hard_plain_n150_B_qwen4b|"
)

run_arm() {
  local repeat="$1" row="$2"
  local label method adapter
  IFS='|' read -r label method adapter <<<"${row}"

  export COST_ARM_LABEL="${label}"
  export METHOD_NAME="${method}"
  export RESEARCH_DB="${OUT}/repeat_${repeat}/${label}.db"
  export RESEARCH_COST_LOG="${OUT}/repeat_${repeat}/${label}.json"
  export HF_BATCH_SIZE=4
  export RESEARCH_COST_WARMUP=1

  if [[ -n "${adapter}" ]]; then
    export LORA_ADAPTER_PATH="${adapter}"
  else
    unset LORA_ADAPTER_PATH || true
  fi

  echo
  echo "============================================================"
  echo "repeat=${repeat} arm=${label} node=$(hostname) gpu=${CUDA_VISIBLE_DEVICES:-unset}"
  echo "started=$(date --iso-8601=seconds)"
  echo "============================================================"
  bash "${ARM_SCRIPT}"
  echo "finished=$(date --iso-8601=seconds)"
}

echo "Controlled sequential cost calibration"
echo "node=$(hostname)"
echo "job=${SLURM_JOB_ID:-none}"
echo "arms=${#ARMS[@]} repeats=3 batch_size=4 warmup=1"
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv,noheader

for repeat in 1 2 3; do
  echo
  echo "#################### REPEAT ${repeat}/3 ####################"

  # Rotate arm order across repeats to reduce order/thermal bias.
  offset=$(( (repeat - 1) * 5 ))
  for step in $(seq 0 14); do
    idx=$(( (offset + step) % 15 ))
    run_arm "${repeat}" "${ARMS[$idx]}"
  done
done

echo
echo "All controlled runs completed."
find "${OUT}" -name '*.json' -type f | sort
