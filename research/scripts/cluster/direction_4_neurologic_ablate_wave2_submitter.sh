#!/bin/bash
# Poll until sbatch accepts the wave-2 catch-up job (under QOS submit limits).
#
# Env:
#   WAVE1_JOBS — colon-separated Slurm job IDs that wave2 must wait on
#                (default: the Jul 2026 wave-1 ablation IDs)
#
# Usage (login node, light poll only — do not run heavy work here):
#   WAVE1_JOBS=263092:263093:... nohup bash research/scripts/cluster/direction_4_neurologic_ablate_wave2_submitter.sh &

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
WAVE1="${WAVE1_JOBS:-263092:263093:263094:263095:263096:263097:263098:263099}"
WAVE2_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_ablate_wave2.sh"
LOG="${PROJECT}/logs/direction_4_ablate_wave2_submitter.log"

mkdir -p "${PROJECT}/logs"
echo "wave2 submitter started $(date -Is) WAVE1=${WAVE1}" | tee -a "${LOG}"

while true; do
  set +e
  OUT=$(sbatch --dependency="afterany:${WAVE1}" \
    --job-name=d4_wave2 \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/direction_4_ablate_wave2_%j.out" \
    "${WAVE2_SCRIPT}" 2>&1)
  RC=$?
  set -e
  if [[ $RC -eq 0 ]]; then
    echo "submitted: ${OUT} $(date -Is)" | tee -a "${LOG}"
    exit 0
  fi
  echo "retry $(date -Is): ${OUT}" | tee -a "${LOG}"
  sleep 120
done
