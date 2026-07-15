#!/bin/bash
# Submit Direction 1.2 Fix-B headline arms on spanish_diagnostic_n150.
# Each arm is its own Slurm job + RESEARCH_DB so the 3 A30 GPUs can run in parallel.
#
# ARM is baked into a small per-arm wrapper (avoids ``sbatch --export=ALL,ARM=...``,
# which this cluster sometimes holds with "user env retrieval failed").
#
# Usage (on the cluster head node):
#   bash research/scripts/cluster/direction_1p2_n150_B_submit.sh
#   INCLUDE_QWEN4B=1 bash research/scripts/cluster/direction_1p2_n150_B_submit.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARM_SCRIPT="${SCRIPT_DIR}/direction_1p2_n150_B_arm_gpu.sh"
PROJECT=/vol/bitbucket/jjg25/LinguistOS
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

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

echo "Submitting ${#ARMS[@]} n150 Fix-B arm(s)..."
JOB_IDS=()
for ARM in "${ARMS[@]}"; do
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
    --gres=gpu:1 \
    --cpus-per-task=6 \
    --partition=a30 \
    --time=24:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/direction_1p2_n150_${ARM}_%j.out" \
    <<EOF
#!/bin/bash
set -euo pipefail
export ARM="${ARM}"
# Arm script's own #SBATCH lines are ignored when executed via bash.
bash "${ARM_SCRIPT}"
EOF
)"
  echo "  ${ARM}: ${OUT}"
  JOB_IDS+=("${OUT##* }")
done

echo ""
echo "Submitted job IDs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
echo "After all succeed, merge with:"
echo "  bash research/scripts/cluster/direction_1p2_n150_B_merge.sh"
echo "Then offline naturalness rescore (PPL + judge) on the per-arm DBs."
