#!/bin/bash
# Merge per-job Diagnostic 5 SQLite files into the canonical research.db.
#
# Submit after all three D5 arms finish:
#   sbatch --dependency=afterok:JOB_A:JOB_B:JOB_C research/scripts/cluster/diagnostic_5_merge.sh

#SBATCH --job-name=d5_merge
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=01:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_5_merge_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
RUNS_DIR="${PROJECT}/research/runs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv" >&2
  exit 1
fi

cd "${PROJECT}"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Diagnostic 5 merge — $(date -Is) ==="
ls -lh "${RUNS_DIR}"/diagnostic_5*.db 2>/dev/null || true

python3 -m research.merge_databases \
  "${RUNS_DIR}/diagnostic_5a.db" \
  "${RUNS_DIR}/diagnostic_5b.db" \
  "${RUNS_DIR}/diagnostic_5c.db"

echo ""
echo "=== Merge done $(date -Is) ==="
