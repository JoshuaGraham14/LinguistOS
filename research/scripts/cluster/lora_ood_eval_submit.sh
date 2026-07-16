#!/bin/bash
# Submit LoRA OOD n36 generation arms in parallel, then PPL+judge on must-run inject arms.
#
# Generation (5 parallel):
#   base:  inject, vanilla, soft
#   LoRA:  inject, vanilla
#
# Naturalness (2 parallel, after their inject gen jobs):
#   inject_base + inject_lora  → fluency_perplexity + naturalness_llm_judge
#
# Usage:
#   bash research/scripts/cluster/lora_ood_eval_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
ADAPTER="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"
RUNS="${PROJECT}/research/runs"

mkdir -p "${PROJECT}/logs" "${RUNS}"

if [[ ! -f "${ADAPTER}/adapter_model.safetensors" ]]; then
  echo "Missing LoRA adapter at ${ADAPTER}" >&2
  exit 1
fi

submit_gen() {
  local name="$1" arm="$2" db="$3"
  local export_vars="ARM=${arm},RESEARCH_DB=${db}"
  if [[ $# -ge 4 ]]; then
    export_vars="${export_vars},LORA_ADAPTER_PATH=${ADAPTER}"
  fi
  # Do not use --export=ALL — Slurm can fail with "user env retrieval failed".
  sbatch \
    --job-name="lora_${name}" \
    --output="${PROJECT}/logs/lora_ood_${name}_%j.out" \
    --export="${export_vars}" \
    "${GEN_SCRIPT}"
}

echo "Submitting OOD generation arms..."

# Capture job IDs
OUT_INJ_BASE=$(submit_gen inj_base inject "${RUNS}/lora_ood_inject_base.db")
OUT_VAN_BASE=$(submit_gen van_base vanilla "${RUNS}/lora_ood_vanilla_base.db")
OUT_SOFT_BASE=$(submit_gen soft_base soft "${RUNS}/lora_ood_soft_base.db")
OUT_INJ_LORA=$(submit_gen inj_lora inject "${RUNS}/lora_ood_inject_lora.db" lora)
OUT_VAN_LORA=$(submit_gen van_lora vanilla "${RUNS}/lora_ood_vanilla_lora.db" lora)

jid() { echo "$1" | awk '{print $NF}'; }

J_INJ_BASE=$(jid "${OUT_INJ_BASE}")
J_VAN_BASE=$(jid "${OUT_VAN_BASE}")
J_SOFT_BASE=$(jid "${OUT_SOFT_BASE}")
J_INJ_LORA=$(jid "${OUT_INJ_LORA}")
J_VAN_LORA=$(jid "${OUT_VAN_LORA}")

echo "  inject_base  job ${J_INJ_BASE}"
echo "  vanilla_base job ${J_VAN_BASE}"
echo "  soft_base    job ${J_SOFT_BASE}"
echo "  inject_lora  job ${J_INJ_LORA}"
echo "  vanilla_lora job ${J_VAN_LORA}"

echo "Submitting naturalness (PPL+judge) chained after must-run inject gens..."

OUT_NAT_BASE=$(sbatch \
  --job-name=lora_nat_inj_b \
  --dependency=afterok:"${J_INJ_BASE}" \
  --output="${PROJECT}/logs/lora_ood_nat_inject_base_%j.out" \
  --export=DB_PATH="${RUNS}/lora_ood_inject_base.db",METHOD_NAME=direction_2_lora_inject_ood_n36,LABEL=inject_base,EVALUATOR=both,RESUME=1 \
  "${NAT_SCRIPT}")

OUT_NAT_LORA=$(sbatch \
  --job-name=lora_nat_inj_l \
  --dependency=afterok:"${J_INJ_LORA}" \
  --output="${PROJECT}/logs/lora_ood_nat_inject_lora_%j.out" \
  --export=DB_PATH="${RUNS}/lora_ood_inject_lora.db",METHOD_NAME=direction_2_lora_inject_ood_n36,LABEL=inject_lora,EVALUATOR=both,RESUME=1 \
  "${NAT_SCRIPT}")

J_NAT_BASE=$(jid "${OUT_NAT_BASE}")
J_NAT_LORA=$(jid "${OUT_NAT_LORA}")

echo "  nat_inject_base job ${J_NAT_BASE} (after ${J_INJ_BASE})"
echo "  nat_inject_lora job ${J_NAT_LORA} (after ${J_INJ_LORA})"
echo "Done submitting."
