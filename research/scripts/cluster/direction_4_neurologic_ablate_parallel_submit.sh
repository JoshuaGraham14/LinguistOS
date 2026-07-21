#!/bin/bash
# Submit Direction 4 Neurologic ablation/tune arms in parallel (one GPU job each,
# one RESEARCH_DB each). Then queue a single naturalness rescore that waits on
# all generation jobs (Slurm afterok:id1:id2:...).
#
# Usage (cluster head node, after code sync):
#   bash research/scripts/cluster/direction_4_neurologic_ablate_parallel_submit.sh

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
ARM_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_ablate_arm_gpu.sh"
NAT_SCRIPT="${PROJECT}/research/scripts/cluster/direction_4_neurologic_ablate_naturalness_gpu.sh"

ARMS=(
  len
  lam03
  group
  prefix
  b4_a50
  b8_a20
  b8_a100
  b16_a50
  b16_a100
  len_lam03
  v2
)

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

# Cluster QOS often caps concurrent submitted jobs (~8). Retry until accepted.
sbatch_with_retry() {
  local arm="$1"
  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    set +e
    OUT="$(sbatch \
      --job-name="d4_${arm}" \
      --gres=gpu:1 \
      --cpus-per-task=4 \
      --partition=a30 \
      --time=12:00:00 \
      --mail-type=ALL \
      --mail-user=jjg25 \
      --output="${PROJECT}/logs/direction_4_ablate_${arm}_%j.out" \
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

echo "Submitting ${#ARMS[@]} parallel Direction 4 Neurologic arms..."
echo "  (one Slurm job + one RESEARCH_DB per arm; retries if QOS submit limit hits)"
JOB_IDS=()
for ARM in "${ARMS[@]}"; do
  OUT="$(sbatch_with_retry "${ARM}")"
  JID="${OUT##* }"
  echo "  ARM=${ARM} -> job ${JID}"
  JOB_IDS+=("${JID}")
done

DEP_LIST=$(IFS=:; echo "${JOB_IDS[*]}")
echo ""
# afterany: still rescore whatever finished if one arm fails
echo "Submitting naturalness rescore afterany:${DEP_LIST}"
NAT_OUT="$(sbatch \
  --dependency="afterany:${DEP_LIST}" \
  "${NAT_SCRIPT}"
)"
echo "  naturalness -> ${NAT_OUT}"
echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Each DB: research/runs/direction_4_smoke5_<arm>.db"
echo "Monitor: squeue -u \$USER"
