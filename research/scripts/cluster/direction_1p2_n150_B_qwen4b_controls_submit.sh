#!/bin/bash
# Queue Qwen3-4B Fix-B controls on n150: vanilla + hard, then PPL+judge rescore.
# Each arm: generation job, then naturalness job with --dependency=afterok.
#
# Usage (cluster):
#   bash research/scripts/cluster/direction_1p2_n150_B_qwen4b_controls_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
GEN_SCRIPT="${PROJECT}/research/scripts/cluster/direction_1p2_n150_B_arm_gpu.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/direction_1p2_n150_B_naturalness_arm.sh"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

ARMS=(
  vanilla_plain_B_qwen4b
  hard_plain_B_qwen4b
)

echo "Submitting Qwen3-4B Fix-B controls (gen → naturalness)..."
for ARM in "${ARMS[@]}"; do
  case "${ARM}" in
    vanilla_plain_B_qwen4b) GEN_NAME=d1n150_van4b; NAT_NAME=d1n150_n_van4b ;;
    hard_plain_B_qwen4b) GEN_NAME=d1n150_hd4b; NAT_NAME=d1n150_n_hd4b ;;
    *) echo "bad arm ${ARM}"; exit 1 ;;
  esac

  GEN_OUT="$(sbatch \
    --job-name="${GEN_NAME}" \
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
export ARM=${ARM}
bash ${GEN_SCRIPT}
EOF
)"
  GEN_ID="${GEN_OUT##* }"
  echo "  GEN  ${ARM}: ${GEN_OUT}"

  NAT_OUT="$(sbatch \
    --job-name="${NAT_NAME}" \
    --dependency=afterok:${GEN_ID} \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=12:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/direction_1p2_n150_natural_${ARM}_%j.out" \
    <<EOF
#!/bin/bash
set -euo pipefail
export ARM=${ARM}
export EVALUATOR=both
export RESUME=0
bash ${NAT_SCRIPT}
EOF
)"
  echo "  NAT  ${ARM}: ${NAT_OUT} (afterok:${GEN_ID})"
done

echo ""
echo "Monitor: squeue -u \$USER"
