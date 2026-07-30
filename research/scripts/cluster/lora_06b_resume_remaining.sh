#!/bin/bash
# Resume after lora06_kick timed out:
#   1) submit any missing gen arms (neuro_inject A/B)
#   2) submit naturalness for all 18 arms
#
# Run from cluster HEAD NODE (no sbatch of this file itself):
#   bash research/scripts/cluster/lora_06b_resume_remaining.sh
#
# Uses heredoc wrappers (no --export=ALL) + QOS retry. Does not touch 1.7B paths.

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/lora_06b_ood_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
LORA_A="${PROJECT}/research/runs/lora_06b/adapters/lora_form"
LORA_B="${PROJECT}/research/runs/lora_06b/adapters/lora_no_inject"
OOD="${PROJECT}/research/runs/lora_06b/ood"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp_06b_resume"
mkdir -p "${PROJECT}/logs" "${OOD}" "${TMPDIR_JOBS}"

for adapter in "${LORA_A}" "${LORA_B}"; do
  if [[ ! -f "${adapter}/adapter_model.safetensors" ]]; then
    echo "Missing LoRA adapter: ${adapter}" >&2
    exit 1
  fi
done

# name|arm|db|adapter|method
ALL_ARMS=(
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

# Known still-queued gen jobs from the timed-out kickoff (name -> jobid)
declare -A LIVE_GEN=(
  [soft_inject_loraA]=268148
  [soft_inject_loraB]=268154
  [neuro_base]=268157
  [neuro_loraA]=268166
  [neuro_loraB]=268172
  [neuro_inject_base]=268221
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

find_running_gen_job() {
  local name="$1"
  # Prefer known map, else look in squeue for l06_${name}
  if [[ -n "${LIVE_GEN[$name]:-}" ]]; then
    # Verify still in queue
    if squeue -j "${LIVE_GEN[$name]}" -h -o '%i' 2>/dev/null | grep -q .; then
      echo "${LIVE_GEN[$name]}"
      return 0
    fi
  fi
  local jid
  jid="$(squeue -u "${USER}" -h -o '%i %j' 2>/dev/null | awk -v n="l06_${name}" '$2==n {print $1; exit}')"
  if [[ -n "${jid}" ]]; then
    echo "${jid}"
  fi
}

echo "=== Phase 1: submit missing gen arms ==="
declare -A GEN_JOB_FOR_NAT=()

for row in "${ALL_ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  live="$(find_running_gen_job "${name}" || true)"
  if [[ -n "${live}" ]]; then
    echo "  ${name}: gen already queued/running as ${live}"
    GEN_JOB_FOR_NAT["${name}"]="${live}"
    continue
  fi
  if [[ -f "${db}" ]]; then
    # Heuristic: completed gen DB present and no live job
    echo "  ${name}: gen DB exists, skip gen resubmit"
    continue
  fi
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
  GEN_JOB_FOR_NAT["${name}"]="${JID}"
done

echo ""
echo "=== Phase 2: submit naturalness for all 18 arms ==="
for row in "${ALL_ARMS[@]}"; do
  IFS='|' read -r name arm db adapter method <<<"${row}"
  SCRIPT="${TMPDIR_JOBS}/nat_${name}.sh"
  write_nat_script "${SCRIPT}" "${name}" "${db}" "${method}"

  dep_args=()
  if [[ -n "${GEN_JOB_FOR_NAT[$name]:-}" ]]; then
    dep_args=(--dependency="afterany:${GEN_JOB_FOR_NAT[$name]}")
    echo -n "  nat ${name} (after ${GEN_JOB_FOR_NAT[$name]}) -> "
  else
    echo -n "  nat ${name} (no dep; gen already done) -> "
  fi

  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="l06nat_${name}" \
    "${dep_args[@]}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_06b_nat_${name}_%j.out"
  )"
  echo "${OUT##* }"
done

echo ""
echo "Done. Monitor: squeue -u \$USER"
