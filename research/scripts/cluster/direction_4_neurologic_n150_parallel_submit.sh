#!/bin/bash
# Submit Direction 4 Neurologic n150 arms in parallel (thin_B + b16_a50),
# then queue naturalness rescore after generation.
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/direction_4_neurologic_n150_parallel_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
ARM_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_n150_arm_gpu.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_n150_naturalness_gpu.sh"

ARMS=(thin_B b16_a50)

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

sbatch_with_retry() {
  local arm="$1"
  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    set +e
    OUT="$(sbatch \
      --job-name="d4n150_${arm}" \
      --gres=gpu:1 \
      --cpus-per-task=4 \
      --partition=a30 \
      --time=48:00:00 \
      --mail-type=ALL \
      --mail-user=jjg25 \
      --output="${PROJECT}/logs/direction_4_n150_${arm}_%j.out" \
      <<EOF
#!/bin/bash
set -euo pipefail
export ARM=${arm}
bash ${ARM_SCRIPT}
EOF
    )"
    RC=$?
    set -e
    if [[ $RC -eq 0 ]]; then
      echo "${OUT}"
      return 0
    fi
    echo "  ARM=${arm} submit blocked (attempt ${attempt}): ${OUT}" >&2
    echo "  waiting 120s for QOS submit/GRES headroom..." >&2
    sleep 120
  done
}

echo "Submitting ${#ARMS[@]} parallel Direction 4 Neurologic n150 arms..."
echo "  (KV-cache speedup commit; one RESEARCH_DB per arm)"
JOB_IDS=()
for ARM in "${ARMS[@]}"; do
  OUT="$(sbatch_with_retry "${ARM}")"
  JID="${OUT##* }"
  echo "  ARM=${ARM} -> job ${JID}"
  JOB_IDS+=("${JID}")
done

DEP_LIST=$(IFS=:; echo "${JOB_IDS[*]}")
echo ""
echo "Submitting naturalness rescore afterany:${DEP_LIST}"
NAT_OUT="$(sbatch \
  --dependency="afterany:${DEP_LIST}" \
  "${NAT_SCRIPT}"
)"
echo "  naturalness -> ${NAT_OUT}"
echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "DBs: research/runs/direction_4_n150_thin_B.db"
echo "     research/runs/direction_4_n150_b16_a50.db"
echo "Compare to: research/runs/direction_1p2_n150_soft_plain_B_beams8.db (etc.)"
echo "Monitor: squeue -u \$USER"
