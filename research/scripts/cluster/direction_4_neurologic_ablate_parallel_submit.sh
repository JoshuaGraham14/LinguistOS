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

echo "Submitting ${#ARMS[@]} parallel Direction 4 Neurologic arms..."
JOB_IDS=()
for ARM in "${ARMS[@]}"; do
  OUT="$(sbatch \
    --job-name="d4_${ARM}" \
    --gres=gpu:1 \
    --cpus-per-task=4 \
    --partition=a30 \
    --time=12:00:00 \
    --mail-type=ALL \
    --mail-user=jjg25 \
    --output="${PROJECT}/logs/direction_4_ablate_${ARM}_%j.out" \
    <<EOF
#!/bin/bash
set -euo pipefail
export ARM=${ARM}
bash ${ARM_SCRIPT}
EOF
  )"
  JID="${OUT##* }"
  echo "  ARM=${ARM} -> job ${JID}"
  JOB_IDS+=("${JID}")
done

DEP_LIST=$(IFS=:; echo "${JOB_IDS[*]}")
echo ""
echo "Submitting naturalness rescore afterok:${DEP_LIST}"
NAT_OUT="$(sbatch \
  --dependency="afterok:${DEP_LIST}" \
  "${NAT_SCRIPT}"
)"
echo "  naturalness -> ${NAT_OUT}"
echo ""
echo "Gen jobs: ${JOB_IDS[*]}"
echo "Monitor: squeue -u \$USER"
