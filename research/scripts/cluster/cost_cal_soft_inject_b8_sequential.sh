#!/bin/bash
# Soft+inject cost calibration at beam width 8, batch size 4.
#
# Fills the three missing Soft+inject rows for the LoRA OOD cost table so it
# matches the eighteen adapter--decode combinations in the quality matrix.
# Uses direction_2_lora_soft_inject_ood_n36 (num_beams: 8), not the older
# Direction 1.2 Base Soft+inject timing at beam 4.
#
#   Base / LoRA-A / LoRA-B  ×  Soft+inject
#   × 3 repeats on one A30, spanish_cost_cal_n36_3verb (93 cells), gen-only.
#
# Outputs:
#   research/runs/cost_cal_soft_inject_b8/repeat_{1,2,3}/*.json
#
# Usage:
#   sbatch research/scripts/cluster/cost_cal_soft_inject_b8_sequential.sh

#SBATCH --job-name=cost_softinj
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=08:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/cost_cal_soft_inject_b8_sequential_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
ARM_SCRIPT="${PROJECT}/research/scripts/cluster/cost_cal_arm.sh"
OUT="${PROJECT}/research/runs/cost_cal_soft_inject_b8"
LORA_A="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"
LORA_B="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_no_inject"
METHOD=direction_2_lora_soft_inject_ood_n36

cd "${PROJECT}"
mkdir -p "${OUT}" "${PROJECT}/logs"

for adapter in "${LORA_A}" "${LORA_B}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    exit 1
  fi
done

# label|adapter (adapter may be empty); method fixed above
ARMS=(
  "base17_soft_inject|"
  "loraA_soft_inject|${LORA_A}"
  "loraB_soft_inject|${LORA_B}"
)

N_ARMS=${#ARMS[@]}

run_arm() {
  local repeat="$1" row="$2"
  local label adapter
  IFS='|' read -r label adapter <<<"${row}"

  export COST_ARM_LABEL="${label}"
  export METHOD_NAME="${METHOD}"
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
  echo "method=${METHOD} batch=${HF_BATCH_SIZE} beams=8"
  echo "started=$(date --iso-8601=seconds)"
  echo "============================================================"
  bash "${ARM_SCRIPT}"
  echo "finished=$(date --iso-8601=seconds)"
}

echo "Soft+inject cost calibration at beam 8 / batch 4"
echo "node=$(hostname)"
echo "job=${SLURM_JOB_ID:-none}"
echo "arms=${N_ARMS} repeats=3 batch_size=4 warmup=1"
echo "out=${OUT}"
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv,noheader

for repeat in 1 2 3; do
  echo
  echo "#################### REPEAT ${repeat}/3 ####################"

  offset=$(( (repeat - 1) ))
  for step in $(seq 0 $((N_ARMS - 1))); do
    idx=$(( (offset + step) % N_ARMS ))
    run_arm "${repeat}" "${ARMS[$idx]}"
  done
done

echo
echo "Soft+inject controlled runs completed."
find "${OUT}" -name '*soft_inject*.json' -type f | sort
