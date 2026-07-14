#!/bin/bash
# Submit per-arm naturalness rescored in parallel (3 A30 GPUs → queue overflow).
# Skips vanilla (already complete). inject: overwrite judge only (keep PPL).
# Other remaining arms: PPL + judge from scratch.
#
# Usage (cluster head node):
#   bash research/scripts/cluster/direction_1p2_n150_B_naturalness_parallel_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
ARM_SCRIPT="${PROJECT}/research/scripts/cluster/direction_1p2_n150_B_naturalness_arm.sh"

mkdir -p "${PROJECT}/logs"

# arm | evaluator | resume | job_name_suffix
# inject: RESUME=0 + judge only → clears judge rows, re-scores judge; leaves PPL intact
# others: both + resume doesn't matter (empty), use RESUME=0 for a clean clear if any junk
JOBS=(
  "inject_plain_B|judge|0|inj"
  "soft_plain_B|both|0|spB4"
  "soft_plain_B_beams8|both|0|spB8"
  "soft_inject_plain_B|both|0|siB"
  "hard_plain_B|both|0|hdB"
  "soft_plain_B_beams8_qwen4b|both|0|spB8_4b"
)

echo "Submitting ${#JOBS[@]} per-arm naturalness jobs..."
JOB_IDS=()
for SPEC in "${JOBS[@]}"; do
  IFS='|' read -r ARM EVALUATOR RESUME SUFFIX <<<"${SPEC}"
  JOB_NAME="d1n150_n_${SUFFIX}"
  OUT="$(sbatch \
    --job-name="${JOB_NAME}" \
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
export EVALUATOR=${EVALUATOR}
export RESUME=${RESUME}
bash ${ARM_SCRIPT}
EOF
)"
  echo "  ${ARM} (evaluator=${EVALUATOR} resume=${RESUME}): ${OUT}"
  JOB_IDS+=("${OUT##* }")
done

echo ""
echo "Submitted: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
