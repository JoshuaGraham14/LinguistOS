#!/bin/bash
# Merge completed Direction 1.2 Fix-B n150 per-arm DBs into research.db.
#
# Run after all core arms finish (optionally include the Qwen4B arm DB if present):
#   bash research/scripts/cluster/direction_1p2_n150_B_merge.sh
# or:
#   sbatch research/scripts/cluster/direction_1p2_n150_B_merge.sh

#SBATCH --job-name=d1n150_merge
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=01:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_n150_B_merge_%j.out

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

DBS=(
  "${RUNS_DIR}/direction_1p2_n150_vanilla_plain_B.db"
  "${RUNS_DIR}/direction_1p2_n150_inject_plain_B.db"
  "${RUNS_DIR}/direction_1p2_n150_soft_plain_B.db"
  "${RUNS_DIR}/direction_1p2_n150_soft_plain_B_beams8.db"
  "${RUNS_DIR}/direction_1p2_n150_soft_inject_plain_B.db"
  "${RUNS_DIR}/direction_1p2_n150_hard_plain_B.db"
)

if [[ -f "${RUNS_DIR}/direction_1p2_n150_soft_plain_B_beams8_qwen4b.db" ]]; then
  DBS+=("${RUNS_DIR}/direction_1p2_n150_soft_plain_B_beams8_qwen4b.db")
fi

echo "=== D1.2 Fix-B n150 merge — $(date -Is) ==="
for db in "${DBS[@]}"; do
  ls -lh "${db}"
done

python3 -m research.merge_databases "${DBS[@]}"

echo "=== merge done $(date -Is) ==="
