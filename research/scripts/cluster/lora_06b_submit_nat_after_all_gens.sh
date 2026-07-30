#!/bin/bash
# Submit ALL 18 naturalness jobs so they start only after ALL still-live
# generation jobs finish (single afterany dependency list).
#
# Run from cluster head node:
#   bash research/scripts/cluster/lora_06b_submit_nat_after_all_gens.sh
#
# Does not resubmit gens. Cancels any existing l06nat_* jobs first.

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
OOD="${PROJECT}/research/runs/lora_06b/ood"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp_06b_nat_after"
mkdir -p "${PROJECT}/logs" "${TMPDIR_JOBS}"

ARMS=(
  "inject_base|direction_2_lora_inject_ood_n36_qwen06b"
  "inject_loraA|direction_2_lora_inject_ood_n36_qwen06b"
  "inject_loraB|direction_2_lora_inject_ood_n36_qwen06b"
  "vanilla_base|direction_2_lora_vanilla_ood_n36_qwen06b"
  "vanilla_loraA|direction_2_lora_vanilla_ood_n36_qwen06b"
  "vanilla_loraB|direction_2_lora_vanilla_ood_n36_qwen06b"
  "soft_base|direction_2_lora_soft_ood_n36_qwen06b"
  "soft_loraA|direction_2_lora_soft_ood_n36_qwen06b"
  "soft_loraB|direction_2_lora_soft_ood_n36_qwen06b"
  "soft_inject_base|direction_2_lora_soft_inject_ood_n36_qwen06b"
  "soft_inject_loraA|direction_2_lora_soft_inject_ood_n36_qwen06b"
  "soft_inject_loraB|direction_2_lora_soft_inject_ood_n36_qwen06b"
  "neuro_base|direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_loraA|direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_loraB|direction_2_lora_neuro_ood_n36_qwen06b"
  "neuro_inject_base|direction_2_lora_neuro_inject_ood_n36_qwen06b"
  "neuro_inject_loraA|direction_2_lora_neuro_inject_ood_n36_qwen06b"
  "neuro_inject_loraB|direction_2_lora_neuro_inject_ood_n36_qwen06b"
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

# Cancel any premature nat jobs
EXISTING_NAT=$(squeue -u "${USER}" -h -o '%i %j' | awk '/l06nat_/ {print $1}' || true)
if [[ -n "${EXISTING_NAT}" ]]; then
  echo "Cancelling existing nat jobs: ${EXISTING_NAT}"
  # shellcheck disable=SC2086
  scancel ${EXISTING_NAT}
  sleep 2
fi

# Collect ALL live generation jobs (l06_* but not l06nat_*)
mapfile -t LIVE_GEN_JIDS < <(squeue -u "${USER}" -h -o '%i %j' | awk '
  $2 ~ /^l06_/ && $2 !~ /^l06nat_/ { print $1 }
')

if [[ ${#LIVE_GEN_JIDS[@]} -eq 0 ]]; then
  echo "No live gen jobs — submitting nat with no dependency (all gens already done)."
  DEP_ARGS=()
else
  DEP_LIST=$(IFS=:; echo "${LIVE_GEN_JIDS[*]}")
  echo "Nat will wait for ALL live gen jobs: ${DEP_LIST}"
  DEP_ARGS=(--dependency="afterany:${DEP_LIST}")
fi

echo ""
echo "Submitting 18 naturalness jobs..."
for row in "${ARMS[@]}"; do
  IFS='|' read -r name method <<<"${row}"
  db="${OOD}/${name}.db"
  SCRIPT="${TMPDIR_JOBS}/nat_${name}.sh"
  {
    echo '#!/bin/bash'
    echo 'set -euo pipefail'
    echo "export DB_PATH=${db}"
    echo "export METHOD_NAME=${method}"
    echo "export LABEL=06b_${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${SCRIPT}"
  chmod +x "${SCRIPT}"

  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="l06nat_${name}" \
    "${DEP_ARGS[@]}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/lora_06b_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* }"
done

echo ""
echo "Done. All nat jobs Dependency=(afterany on remaining gens) until those finish."
squeue -u "${USER}" -o '%.18i %.26j %.2t %R'
