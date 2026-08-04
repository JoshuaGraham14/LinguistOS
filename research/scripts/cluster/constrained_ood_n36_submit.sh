#!/bin/bash
# Submit constrained-decoding OOD n36 arms, then PPL + LLM-judge.
#
# Arms (per-arm RESEARCH_DB; never touches existing DBs or jobs):
#   hard, hard_best, bias2, bias8, bias12, vanilla_4b, soft_4b
#
# Soft bias=5 already exists as lora_ood_soft_base.db — not re-run.
#
# Reuses lora_ood_naturalness_arm.sh for naturalness.
# Does NOT cancel or modify any other jobs.
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/constrained_ood_n36_submit.sh
#
# Playbook: one RESEARCH_DB per arm; never rsync *.db; skip experiment-wide metrics.
# Important: do NOT use --export=ALL (Slurm "user env retrieval failed").

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/constrained_ood_n36_eval_arm.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/lora_ood_naturalness_arm.sh"
RUNS="${PROJECT}/research/runs"
TMPDIR_JOBS="${PROJECT}/logs/sbatch_tmp"
mkdir -p "${PROJECT}/logs" "${RUNS}" "${TMPDIR_JOBS}"

# name|arm|db|method
ARMS=(
  "hard|hard|${RUNS}/constrained_ood_n36_hard.db|direction_1a_hard_plain_ood_n36"
  "hard_best|hard_best|${RUNS}/constrained_ood_n36_hard_best.db|direction_1a_hard_plain_best_ood_n36"
  "bias2|bias2|${RUNS}/constrained_ood_n36_bias2.db|direction_1b_soft_plain_ood_n36_bias2"
  "bias8|bias8|${RUNS}/constrained_ood_n36_bias8.db|direction_1b_soft_plain_ood_n36_bias8"
  "bias12|bias12|${RUNS}/constrained_ood_n36_bias12.db|direction_1b_soft_plain_ood_n36_bias12"
  "vanilla_4b|vanilla_4b|${RUNS}/constrained_ood_n36_vanilla_4b.db|direction_1_vanilla_plain_ood_n36_qwen4b"
  "soft_4b|soft_4b|${RUNS}/constrained_ood_n36_soft_4b.db|direction_1b_soft_plain_ood_n36_qwen4b"
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
    echo "export LABEL=constrained_ood_${name}"
    echo 'export EVALUATOR=both'
    echo 'export RESUME=1'
    echo "bash ${NAT_SCRIPT}"
  } >"${path}"
  chmod +x "${path}"
}

echo "Submitting constrained-decoding OOD n36 (7 arms)..."
echo "Existing queue (will not cancel/modify):"
squeue --me || true
echo ""

JOB_IDS=()
NAT_SPECS=()
for row in "${ARMS[@]}"; do
  IFS='|' read -r name arm db method <<<"${row}"
  if [[ -e "${db}" ]]; then
    echo "REFUSING: DB already exists: ${db}" >&2
    echo "  (will not overwrite; rename/move it first if a fresh run is intended)" >&2
    exit 1
  fi
  SCRIPT="${TMPDIR_JOBS}/gen_constrained_ood_${name}.sh"
  write_gen_script "${SCRIPT}" "${arm}" "${db}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="d1_${name}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/constrained_ood_n36_${name}_%j.out"
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
  SCRIPT="${TMPDIR_JOBS}/nat_constrained_ood_${name}.sh"
  write_nat_script "${SCRIPT}" "${name}" "${db}" "${method}"
  OUT="$(sbatch_script_with_retry "${SCRIPT}" \
    --job-name="d1_nat_${name}" \
    --dependency="afterok:${jid}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=06:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/constrained_ood_n36_nat_${name}_%j.out"
  )"
  echo "  nat ${name} -> ${OUT##* } (afterok ${jid})"
done

echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
echo "DBs (new only; existing soft bias=5 / vanilla 1.7B untouched):"
for row in "${ARMS[@]}"; do
  IFS='|' read -r _ _ db _ <<<"${row}"
  echo "  ${db}"
done
