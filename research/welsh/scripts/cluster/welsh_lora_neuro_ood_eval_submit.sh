#!/bin/bash
# Submit Welsh thin-Neurologic OOD n36 generation + naturalness (PPL + LLM judge).
#
# Four arms (new DBs; does not overwrite greedy Welsh OOD results):
#   neuro_vanilla_base
#   neuro_inject_base
#   neuro_vanilla_lora_no_inject
#   neuro_inject_lora_form
#
# Usage (cluster head node, after code sync):
#   bash research/welsh/scripts/cluster/welsh_lora_neuro_ood_eval_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
GEN_SCRIPT="${PROJECT}/research/welsh/scripts/cluster/welsh_lora_neuro_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/welsh_lora_ood_naturalness_arm.sh"
LORA_NO_INJECT="${PROJECT}/research/runs/lora_welsh/adapters/qwen3_1p7b_lora_no_inject_balanced_2k_each"
LORA_FORM="${PROJECT}/research/runs/lora_welsh/adapters/qwen3_1p7b_lora_form_balanced_2k_each"
RUNS="${PROJECT}/research/runs/lora_welsh/ood"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp"
mkdir -p "${PROJECT}/logs" "${RUNS}" "${TMPDIR_JOBS}"

for adapter in "${LORA_NO_INJECT}" "${LORA_FORM}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    exit 1
  fi
done
if [[ ! -f "${PROJECT}/research/benchmarks/welsh_transfer_ood_n36.yaml" ]]; then
  echo "Missing OOD benchmark: ${PROJECT}/research/benchmarks/welsh_transfer_ood_n36.yaml" >&2
  exit 1
fi
if [[ ! -f "${GEN_SCRIPT}" ]]; then
  echo "Missing gen script: ${GEN_SCRIPT}" >&2
  exit 1
fi

# name|arm|db|adapter_or_empty|method
ARMS=(
  "neuro_vanilla_base|vanilla|${RUNS}/welsh_lora_ood_neuro_vanilla_base.db||welsh_lora_neuro_vanilla_ood_n36"
  "neuro_inject_base|inject|${RUNS}/welsh_lora_ood_neuro_inject_base.db||welsh_lora_neuro_inject_ood_n36"
  "neuro_vanilla_lora_no_inject|vanilla|${RUNS}/welsh_lora_ood_neuro_vanilla_lora_no_inject.db|${LORA_NO_INJECT}|welsh_lora_neuro_vanilla_ood_n36"
  "neuro_inject_lora_form|inject|${RUNS}/welsh_lora_ood_neuro_inject_lora_form.db|${LORA_FORM}|welsh_lora_neuro_inject_ood_n36"
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
    echo "export LABEL=welsh_ood_${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

echo "=== QUEUE BEFORE ==="
squeue --me -o "%.18i %.9P %.28j %.8u %.2t %R" || true
echo ""

echo "Submitting Welsh Neurologic OOD gen arms..."
declare -A GEN_JIDS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  if [[ -e "${db}" ]]; then
    echo "REFUSING: DB already exists: ${db}" >&2
    exit 1
  fi
  if squeue --me -h -o '%j' | grep -qx "cy_${name}"; then
    echo "  skip ${name}: already in queue"
    continue
  fi
  SCRIPT="${TMPDIR_JOBS}/gen_welsh_ood_${name}.sh"
  write_gen_script "${SCRIPT}" "${arm}" "${db}" "${adapter}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="cy_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=48:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/welsh_lora_ood_${name}_%j.out"
  )"
  JID="${OUT##* }"
  GEN_JIDS[$name]="${JID}"
  echo "  ${name} -> job ${JID}  DB=$(basename "${db}")"
done

echo ""
echo "Submitting naturalness (PPL + Welsh LLM judge) afterok each gen..."
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  jid="${GEN_JIDS[$name]:-}"
  if [[ -z "${jid}" ]]; then
    echo "  skip nat ${name}: no gen job id"
    continue
  fi
  if squeue --me -h -o '%j' | grep -qx "cy_nat_${name}"; then
    echo "  skip nat ${name}: already in queue"
    continue
  fi
  SCRIPT="${TMPDIR_JOBS}/nat_welsh_ood_${name}.sh"
  write_nat_script "${SCRIPT}" "${name}" "${db}" "${method}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="cy_nat_${name}" \
    --dependency="afterok:${jid}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/welsh_lora_ood_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* } (afterok ${jid})"
done

echo ""
echo "=== QUEUE AFTER ==="
squeue --me -o "%.18i %.9P %.28j %.8u %.2t %.10M %R"
