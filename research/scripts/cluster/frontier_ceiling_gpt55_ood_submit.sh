#!/bin/bash
# Submit Phase A (gen on t4) then Phase B (nat on a30) with afterok dependency.
# Run from the frontier-gpt55 cluster checkout (or any clone of this branch).
#
# Usage (on gpucluster2 head node):
#   bash research/scripts/cluster/frontier_ceiling_gpt55_ood_submit.sh

set -euo pipefail

PROJECT="${PROJECT:-/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55}"
cd "${PROJECT}"

GEN_SCRIPT="${PROJECT}/research/scripts/cluster/frontier_ceiling_gpt55_ood_gen.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/frontier_ceiling_gpt55_ood_nat.sh"
DB_PATH="${PROJECT}/research/runs/frontier_ceiling_gpt55_vanilla_ood_n36.db"

mkdir -p "${PROJECT}/logs" "$(dirname "${DB_PATH}")"

chmod +x "${GEN_SCRIPT}" "${NAT_SCRIPT}"

echo "Submitting gen → ${DB_PATH}"
GEN_JOB=$(sbatch --parsable "${GEN_SCRIPT}")
echo "  gen job: ${GEN_JOB}"

echo "Submitting nat (afterok:${GEN_JOB})"
NAT_JOB=$(sbatch --parsable \
  --dependency=afterok:"${GEN_JOB}" \
  --export=ALL,DB_PATH="${DB_PATH}" \
  "${NAT_SCRIPT}")
echo "  nat job: ${NAT_JOB}"

echo "Monitor: squeue --me"
echo "Logs: ${PROJECT}/logs/frontier_ceiling_gpt55_ood_*.out"
