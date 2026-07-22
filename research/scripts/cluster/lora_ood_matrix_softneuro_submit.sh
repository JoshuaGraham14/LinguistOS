#!/bin/bash
# Submit LoRA OOD soft_inject B8 + Neurologic B16 (+inject) arms
# (Base / LoRA-A / LoRA-B) in parallel, then queue naturalness after generation.
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/lora_ood_matrix_softneuro_submit.sh
#
# Playbook: one RESEARCH_DB per arm; never rsync *.db; --skip-experiment-group-metrics
# is already set in lora_ood_eval_arm.sh.
#
# Important: do NOT use --export=ALL or --export=VAR=val for these jobs.
# Slurm on this cluster can hold jobs with "user env retrieval failed".
# Env is set inside a heredoc wrapper instead (same pattern as Neurologic n150).
# QOS retry rewrites a temp job script each attempt so the heredoc is not
# consumed empty on retry.

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
LORA_A="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"
LORA_B="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_no_inject"
RUNS="${PROJECT}/research/runs"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp"
mkdir -p "${PROJECT}/logs" "${RUNS}" "${TMPDIR_JOBS}"

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
  "neuro_inject_base|neuro_inject|${RUNS}/lora_ood_neuro_inject_base.db||direction_2_lora_neuro_inject_ood_n36"
  "neuro_inject_lora|neuro_inject|${RUNS}/lora_ood_neuro_inject_lora.db|${LORA_A}|direction_2_lora_neuro_inject_ood_n36"
  "neuro_inject_lora_no_inject|neuro_inject|${RUNS}/lora_ood_neuro_inject_lora_no_inject.db|${LORA_B}|direction_2_lora_neuro_inject_ood_n36"
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
    echo "export LABEL=${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

echo "Submitting LoRA OOD soft_inject B8 + Neurologic B16 (+inject) matrix arms..."
JOB_IDS=()
NAT_SPECS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  SCRIPT="${TMPDIR_JOBS}/gen_${name}.sh"
  write_gen_script "${SCRIPT}" "${arm}" "${db}" "${adapter}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="lora_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_ood_${name}_%j.out"
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
    --job-name="lora_nat_${name}" \
    --dependency="afterany:${jid}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_ood_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* } (after ${jid})"
done

echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
