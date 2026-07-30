#!/bin/bash
# Submit full Qwen3-0.6B LoRA OOD matrix:
#   Base / LoRA-A (form) / LoRA-B (no-inject)  ×  6 decode arms
# Then queue naturalness (PPL + LLM judge) after each gen job.
#
# Writes ONLY under research/runs/lora_06b/ood/ — does not touch 1.7B DBs.
#
# Usage (cluster head node, after both 0.6B adapters exist):
#   bash research/scripts/cluster/lora_06b_matrix_submit.sh
#
# Playbook: one RESEARCH_DB per arm; never rsync *.db; no --export=ALL
# (heredoc wrappers + QOS retry, same pattern as lora_ood_matrix_softneuro_submit.sh).

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/lora_06b_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
LORA_A="${PROJECT}/research/runs/lora_06b/adapters/lora_form"
LORA_B="${PROJECT}/research/runs/lora_06b/adapters/lora_no_inject"
OOD="${PROJECT}/research/runs/lora_06b/ood"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp_06b"
mkdir -p "${PROJECT}/logs" "${OOD}" "${TMPDIR_JOBS}"

for adapter in "${LORA_A}" "${LORA_B}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    echo "Train first: sbatch research/scripts/cluster/lora_06b_sft_form.sh" >&2
    echo "             sbatch research/scripts/cluster/lora_06b_sft_no_inject.sh" >&2
    exit 1
  fi
done

# name|arm|db|adapter_or_empty|method
ARMS=(
  "inject_base|inject|${OOD}/inject_base.db||direction_2_lora_inject_ood_n36_qwen06b"
  "inject_loraA|inject|${OOD}/inject_loraA.db|${LORA_A}|direction_2_lora_inject_ood_n36_qwen06b"
  "inject_loraB|inject|${OOD}/inject_loraB.db|${LORA_B}|direction_2_lora_inject_ood_n36_qwen06b"
  "vanilla_base|vanilla|${OOD}/vanilla_base.db||direction_2_lora_vanilla_ood_n36_qwen06b"
  "vanilla_loraA|vanilla|${OOD}/vanilla_loraA.db|${LORA_A}|direction_2_lora_vanilla_ood_n36_qwen06b"
  "vanilla_loraB|vanilla|${OOD}/vanilla_loraB.db|${LORA_B}|direction_2_lora_vanilla_ood_n36_qwen06b"
  "soft_base|soft|${OOD}/soft_base.db||direction_2_lora_soft_ood_n36_qwen06b"
  "soft_loraA|soft|${OOD}/soft_loraA.db|${LORA_A}|direction_2_lora_soft_ood_n36_qwen06b"
  "soft_loraB|soft|${OOD}/soft_loraB.db|${LORA_B}|direction_2_lora_soft_ood_n36_qwen06b"
  "soft_inject_base|soft_inject|${OOD}/soft_inject_base.db||direction_2_lora_soft_inject_ood_n36_qwen06b"
  "soft_inject_loraA|soft_inject|${OOD}/soft_inject_loraA.db|${LORA_A}|direction_2_lora_soft_inject_ood_n36_qwen06b"
  "soft_inject_loraB|soft_inject|${OOD}/soft_inject_loraB.db|${LORA_B}|direction_2_lora_soft_inject_ood_n36_qwen06b"
  "neuro_base|neuro|${OOD}/neuro_base.db||direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_loraA|neuro|${OOD}/neuro_loraA.db|${LORA_A}|direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_loraB|neuro|${OOD}/neuro_loraB.db|${LORA_B}|direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_inject_base|neuro_inject|${OOD}/neuro_inject_base.db||direction_2_lora_neuro_inject_ood_n36_qwen06b"
  "neuro_inject_loraA|neuro_inject|${OOD}/neuro_inject_loraA.db|${LORA_A}|direction_2_lora_neuro_inject_ood_n36_qwen06b"
  "neuro_inject_loraB|neuro_inject|${OOD}/neuro_inject_loraB.db|${LORA_B}|direction_2_lora_neuro_inject_ood_n36_qwen06b"
)

sbatch_script_with_retry() {
  local job_script="$1"
  shift
  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    set +e
    OUT="$(sbatch "$@" "${job_script}" 2>&1)"
    RC=$?
    set -e
    if [[ $RC -eq 0 ]]; then
      echo "${OUT}"
      return 0
    fi
    echo "  submit blocked (attempt ${attempt}): ${OUT}" >&2
    echo "  waiting 120s for QOS submit/GRES headroom..." >&2
    sleep 120
  done
}

write_gen_script() {
  local path="$1" arm="$2" db="$3" adapter="$4"
  {
    echo '#!/bin/bash'
    echo 'set -euo pipefail'
    echo "export ARM=${arm}"
    echo "export RESEARCH_DB=${db}"
    if [[ -n "${adapter}" ]]; then
      echo "export LORA_ADAPTER_PATH=${adapter}"
    else
      echo 'unset LORA_ADAPTER_PATH || true'
    fi
    echo "bash ${GEN_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

write_nat_script() {
  local path="$1" name="$2" db="$3" method="$4"
  {
    echo '#!/bin/bash'
    echo 'set -euo pipefail'
    echo "export DB_PATH=${db}"
    echo "export METHOD_NAME=${method}"
    echo "export LABEL=06b_${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

echo "Submitting Qwen3-0.6B LoRA OOD matrix (18 arms)..."
JOB_IDS=()
NAT_SPECS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  SCRIPT="${TMPDIR_JOBS}/gen_${name}.sh"
  write_gen_script "${SCRIPT}" "${arm}" "${db}" "${adapter}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="l06_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_06b_ood_${name}_%j.out"
  )"
  JID="${OUT##* }"
  echo "  ${name} -> job ${JID}  DB=$(basename "${db}")"
  JOB_IDS+=("${JID}")
  NAT_SPECS+=("${JID}|${name}|${db}|${method}")
done

echo ""
echo "Submitting naturalness after each gen (afterany)..."
for spec in "${NAT_SPECS[@]}"; do
  IFS='|' read -r jid name db method <<<"${spec}"
  SCRIPT="${TMPDIR_JOBS}/nat_${name}.sh"
  write_nat_script "${SCRIPT}" "${name}" "${db}" "${method}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="l06nat_${name}" \
    --dependency="afterany:${jid}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_06b_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* } (after ${jid})"
done

echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
echo "DBs: ${OOD}/"
