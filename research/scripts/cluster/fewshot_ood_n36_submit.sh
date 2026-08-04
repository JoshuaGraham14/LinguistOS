#!/bin/bash
# Submit few-shot static + dynamic OOD n36 generation, then PPL + LLM-judge.
#
# Reuses lora_ood_naturalness_arm.sh for naturalness (generic DB/METHOD_NAME).
# Does NOT cancel or modify any other jobs.
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/fewshot_ood_n36_submit.sh
#
# Playbook: one RESEARCH_DB per arm; never rsync *.db; skip experiment-wide metrics.
# Important: do NOT use --export=ALL (Slurm "user env retrieval failed").

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/fewshot_ood_n36_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
RUNS="${PROJECT}/research/runs"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp"
mkdir -p "${PROJECT}/logs" "${RUNS}" "${TMPDIR_JOBS}"

# name|arm|db|method
ARMS=(
  "static|static|${RUNS}/fewshot_ood_n36_static.db|direction_5_fewshot_static_k3_ood_n36"
  "dynamic|dynamic|${RUNS}/fewshot_ood_n36_dynamic.db|direction_5_fewshot_dynamic_k3_ood_n36"
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
  local path="$1" arm="$2" db="$3"
  {
    echo '#!/bin/bash'
    echo 'set -euo pipefail'
    echo "export ARM=${arm}"
    echo "export RESEARCH_DB=${db}"
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
    echo "export LABEL=fewshot_ood_${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

echo "Submitting few-shot OOD n36 (static + dynamic)..."
echo "Existing queue (will not cancel/modify):"
squeue --me || true
echo ""

JOB_IDS=()
NAT_SPECS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db method <<<"${row}"
  SCRIPT="${TMPDIR_JOBS}/gen_fewshot_ood_${name}.sh"
  write_gen_script "${SCRIPT}" "${arm}" "${db}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="fs_ood_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/fewshot_ood_n36_${name}_%j.out"
  )"
  JID="${OUT##* }"
  echo "  ${name} -> job ${JID}  DB=$(basename "${db}")"
  JOB_IDS+=("${JID}")
  NAT_SPECS+=("${JID}|${name}|${db}|${method}")
done

echo ""
echo "Submitting PPL + LLM-judge naturalness after each gen (afterok)..."
for spec in "${NAT_SPECS[@]}"; do
  IFS='|' read -r jid name db method <<<"${spec}"
  SCRIPT="${TMPDIR_JOBS}/nat_fewshot_ood_${name}.sh"
  write_nat_script "${SCRIPT}" "${name}" "${db}" "${method}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="fs_ood_nat_${name}" \
    --dependency="afterok:${jid}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/fewshot_ood_n36_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* } (afterok ${jid})"
done

echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
echo "DBs:"
echo "  ${RUNS}/fewshot_ood_n36_static.db"
echo "  ${RUNS}/fewshot_ood_n36_dynamic.db"
