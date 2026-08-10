#!/bin/bash
# Controlled Neuro / Neuro+inject cost calibration extension.
#
# Adds the six missing arms from the LoRA OOD quality matrix onto the same
# protocol as cost_cal_sequential.sh:
#   Base / LoRA-A / LoRA-B  ×  Neuro / Neuro+inject
#   × 3 repeats on one A30, spanish_cost_cal_n36_3verb (93 cells), gen-only.
#
# Method YAMLs match the OOD quality matrix (direction_2_lora_neuro_*_ood_n36).
# HF_BATCH_SIZE=1 matches those OOD eval arms (beam 16 NeuroLogic memory).
# Outputs land alongside the existing calibration JSONs under
# research/runs/cost_cal_sequential/repeat_{1,2,3}/.
#
# Usage:
#   sbatch research/scripts/cluster/cost_cal_neuro_sequential.sh

#SBATCH --job-name=cost_neuro6
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=18:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/cost_cal_neuro_sequential_%j.out

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
# Must: A/B Neuro + Neuro+inject. Nice: Base Neuro + Neuro+inject.
ARMS=(
  "base17_neuro|direction_2_lora_neuro_ood_n36|"
  "base17_neuro_inject|direction_2_lora_neuro_inject_ood_n36|"
  "loraA_neuro|direction_2_lora_neuro_ood_n36|${LORA_A}"
  "loraA_neuro_inject|direction_2_lora_neuro_inject_ood_n36|${LORA_A}"
  "loraB_neuro|direction_2_lora_neuro_ood_n36|${LORA_B}"
  "loraB_neuro_inject|direction_2_lora_neuro_inject_ood_n36|${LORA_B}"
)

N_ARMS=${#ARMS[@]}

run_arm() {
  local repeat="$1" row="$2"
  local label method adapter
  IFS='|' read -r label method adapter <<<"${row}"

  export COST_ARM_LABEL="${label}"
  export METHOD_NAME="${method}"
  export RESEARCH_DB="${OUT}/repeat_${repeat}/${label}.db"
  export RESEARCH_COST_LOG="${OUT}/repeat_${repeat}/${label}.json"
  # Match OOD Neuro eval arms (beam 16); do not use the Soft/Vanilla batch=4 default.
  export HF_BATCH_SIZE=1
  export RESEARCH_COST_WARMUP=1

  if [[ -n "${adapter}" ]]; then
    export LORA_ADAPTER_PATH="${adapter}"
  else
    unset LORA_ADAPTER_PATH || true
  fi

  echo
  echo "============================================================"
  echo "repeat=${repeat} arm=${label} node=$(hostname) gpu=${CUDA_VISIBLE_DEVICES:-unset}"
  echo "method=${method} batch=${HF_BATCH_SIZE}"
  echo "started=$(date --iso-8601=seconds)"
  echo "============================================================"
  bash "${ARM_SCRIPT}"
  echo "finished=$(date --iso-8601=seconds)"
}

echo "Controlled Neuro cost calibration extension"
echo "node=$(hostname)"
echo "job=${SLURM_JOB_ID:-none}"
echo "arms=${N_ARMS} repeats=3 batch_size=1 warmup=1"
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv,noheader

for repeat in 1 2 3; do
  echo
  echo "#################### REPEAT ${repeat}/3 ####################"

  # Rotate arm order across repeats (same idea as cost_cal_sequential.sh).
  offset=$(( (repeat - 1) * 2 ))
  for step in $(seq 0 $((N_ARMS - 1))); do
    idx=$(( (offset + step) % N_ARMS ))
    run_arm "${repeat}" "${ARMS[$idx]}"
  done
done

echo
echo "Neuro controlled runs completed."
find "${OUT}" -name '*neuro*.json' -type f | sort
