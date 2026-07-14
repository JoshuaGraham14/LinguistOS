#!/bin/bash
# Submit Direction 1.2 Fix-B headline arms on spanish_diagnostic_n150.
# Each arm is its own Slurm job + RESEARCH_DB so the 3 A30 GPUs can run in parallel.
#
# Usage (from any machine with SSH to the cluster head node, or on the head node):
#   bash research/scripts/cluster/direction_1p2_n150_B_submit.sh
#   INCLUDE_QWEN4B=1 bash research/scripts/cluster/direction_1p2_n150_B_submit.sh
#
# Core 1.7B arms (default):
#   vanilla_plain_B, inject_plain_B, soft_plain_B (beams=4),
#   soft_plain_B_beams8, soft_inject_plain_B, hard_plain_B
#
# Optional later:
#   soft_plain_B_beams8_qwen4b  (set INCLUDE_QWEN4B=1)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM_SCRIPT="${SCRIPT_DIR}/direction_1p2_n150_B_arm_gpu.sh"
INCLUDE_QWEN4B="${INCLUDE_QWEN4B:-0}"

CORE_ARMS=(
  vanilla_plain_B
  inject_plain_B
  soft_plain_B
  soft_plain_B_beams8
  soft_inject_plain_B
  hard_plain_B
)

ARMS=("${CORE_ARMS[@]}")
if [[ "${INCLUDE_QWEN4B}" == "1" ]]; then
  ARMS+=(soft_plain_B_beams8_qwen4b)
fi

echo "Submitting ${#ARMS[@]} n150 Fix-B arm(s)..."
JOB_IDS=()
for ARM in "${ARMS[@]}"; do
  # Short, unique job names for squeue readability
  case "${ARM}" in
    vanilla_plain_B) JOB_NAME=d1n150_vanB ;;
    inject_plain_B) JOB_NAME=d1n150_injB ;;
    soft_plain_B) JOB_NAME=d1n150_spB4 ;;
    soft_plain_B_beams8) JOB_NAME=d1n150_spB8 ;;
    soft_inject_plain_B) JOB_NAME=d1n150_siB ;;
    hard_plain_B) JOB_NAME=d1n150_hdB ;;
    soft_plain_B_beams8_qwen4b) JOB_NAME=d1n150_spB8_4b ;;
    *) JOB_NAME="d1n150_${ARM}" ;;
  esac

  OUT="$(sbatch \
    --job-name="${JOB_NAME}" \
    --export=ALL,ARM="${ARM}" \
    --output="/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_n150_${ARM}_%j.out" \
    "${ARM_SCRIPT}")"
  echo "  ${ARM}: ${OUT}"
  JOB_IDS+=("${OUT##* }")
done

echo ""
echo "Submitted job IDs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
echo "After all succeed, merge with:"
echo "  python3 -m research.merge_databases research/runs/direction_1p2_n150_*.db"
echo "Then offline naturalness rescore (PPL + judge) on the per-arm DBs."
