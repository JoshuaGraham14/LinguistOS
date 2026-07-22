#!/bin/bash
# Submit LoRA OOD soft_inject B8 + Neurologic B16 arms (Base / LoRA-A / LoRA-B)
# in parallel, then queue naturalness (PPL + LLM judge) after generation.
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/lora_ood_matrix_softneuro_submit.sh
#
# Playbook: one RESEARCH_DB per arm; never rsync *.db; --skip-experiment-group-metrics
# is already set in lora_ood_eval_arm.sh. Do not use --export=ALL.

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
LORA_A="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"
LORA_B="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_no_inject"
RUNS="${PROJECT}/research/runs"

mkdir -p "${PROJECT}/logs" "${RUNS}"

for adapter in "${LORA_A}" "${LORA_B}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    exit 1
  fi
done

# name|arm|db|adapter_or_empty|method
ARMS=(
  "soft_inject_base|soft_inject|${RUNS}/lora_ood_soft_inject_base.db||direction_2_lora_soft_inject_ood_n36"
  "soft_inject_lora|soft_inject|${RUNS}/lora_ood_soft_inject_lora.db|${LORA_A}|direction_2_lora_soft_inject_ood_n36"
  "soft_inject_lora_no_inject|soft_inject|${RUNS}/lora_ood_soft_inject_lora_no_inject.db|${LORA_B}|direction_2_lora_soft_inject_ood_n36"
  "neuro_base|neuro|${RUNS}/lora_ood_neuro_base.db||direction_2_lora_neuro_ood_n36"
  "neuro_lora|neuro|${RUNS}/lora_ood_neuro_lora.db|${LORA_A}|direction_2_lora_neuro_ood_n36"
  "neuro_lora_no_inject|neuro|${RUNS}/lora_ood_neuro_lora_no_inject.db|${LORA_B}|direction_2_lora_neuro_ood_n36"
)

sbatch_gen() {
  local name="$1" arm="$2" db="$3" adapter="$4"
  # Selective exports only — do not use --export=ALL (Slurm env retrieval failures).
  local export_vars="ARM=${arm},RESEARCH_DB=${db}"
  if [[ -n "${adapter}" ]]; then
    export_vars="${export_vars},LORA_ADAPTER_PATH=${adapter}"
  fi
  sbatch \
    --job-name="lora_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_ood_${name}_%j.out" \
    --export="${export_vars}" \
    "${GEN_SCRIPT}"
}

echo "Submitting LoRA OOD soft_inject B8 + Neurologic B16 matrix arms..."
JOB_IDS=()
NAT_SPECS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  OUT="$(sbatch_gen "${name}" "${arm}" "${db}" "${adapter}")"
  JID="${OUT##* }"
  echo "  ${name} -> job ${JID}  DB=$(basename "${db}")"
  JOB_IDS+=("${JID}")
  NAT_SPECS+=("${JID}|${name}|${db}|${method}")
done

echo ""
echo "Submitting naturalness after each gen (afterany)..."
for spec in "${NAT_SPECS[@]}"; do
  IFS='|' read -r jid name db method <<<"${spec}"
  OUT="$(sbatch \
    --job-name="lora_nat_${name}" \
    --dependency="afterany:${jid}" \
    --output="${PROJECT}/logs/lora_ood_nat_${name}_%j.out" \
    --export="DB_PATH=${db},METHOD_NAME=${method},LABEL=${name},EVALUATOR=both,RESUME=1" \
    "${NAT_SCRIPT}"
  )"
  echo "  nat ${name} -> ${OUT##* } (after ${jid})"
done

echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
