#!/bin/bash
# Wait until the user's Slurm submit-count has headroom, then submit
# frontier GPT-5.5 gen + nat. NEVER cancels or modifies other jobs.
#
# Usage (head node, background):
#   nohup bash research/scripts/cluster/frontier_ceiling_gpt55_ood_submit_when_ready.sh \
#     > logs/frontier_ceiling_gpt55_submit_waiter.out 2>&1 &

set -euo pipefail

PROJECT="${PROJECT:-/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55}"
cd "${PROJECT}"
mkdir -p logs research/runs

GEN_SCRIPT="${PROJECT}/research/scripts/cluster/frontier_ceiling_gpt55_ood_gen.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/frontier_ceiling_gpt55_ood_nat.sh"
DB_PATH="${PROJECT}/research/runs/frontier_ceiling_gpt55_vanilla_ood_n36.db"
MARKER="${PROJECT}/logs/frontier_ceiling_gpt55_submitted.ok"
POLL_SECS="${POLL_SECS:-180}"
# Leave room for gen + nat (2 jobs). Limit observed as 8 total for this QOS.
MAX_OTHER="${MAX_OTHER:-6}"

if [[ -f "${MARKER}" ]]; then
  echo "Already submitted ($(cat "${MARKER}")). Exiting."
  exit 0
fi

chmod +x "${GEN_SCRIPT}" "${NAT_SCRIPT}"

echo "=== wait-and-submit started $(date -Is) ==="
echo "Will submit when squeue --me count <= ${MAX_OTHER} (need +2 slots)."
echo "NEVER cancels jobs. Poll every ${POLL_SECS}s."

while true; do
  # Count only; do not touch other jobs.
  N=$(squeue --me -h 2>/dev/null | wc -l | tr -d ' ')
  echo "$(date -Is) queue_count=${N} need_le=${MAX_OTHER}"

  if [[ "${N}" -le "${MAX_OTHER}" ]]; then
    echo "Headroom available — submitting frontier ceiling jobs only."
    GEN_JOB=$(sbatch --parsable "${GEN_SCRIPT}")
    echo "SUBMITTED_GEN=${GEN_JOB}"
    NAT_JOB=$(sbatch --parsable \
      --dependency=afterok:"${GEN_JOB}" \
      --export=ALL,DB_PATH="${DB_PATH}" \
      "${NAT_SCRIPT}")
    echo "SUBMITTED_NAT=${NAT_JOB}"
    echo "gen=${GEN_JOB} nat=${NAT_JOB} at $(date -Is)" > "${MARKER}"
    squeue --me -o "%.18i %.9P %.30j %.2t %R"
    echo "=== done ==="
    exit 0
  fi
  sleep "${POLL_SECS}"
done
