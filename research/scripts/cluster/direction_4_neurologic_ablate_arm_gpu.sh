#!/bin/bash
# Direction 4 Neurologic ablation/tune arm — one Slurm job = one RESEARCH_DB.
#
# Required env:
#   ARM — short key (see case below)
#
# Usage (prefer the parallel submit wrapper):
#   ARM=len sbatch research/scripts/cluster/direction_4_neurologic_ablate_arm_gpu.sh

#SBATCH --job-name=d4_abl
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_ablate_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

: "${ARM:?Set ARM (e.g. len). Prefer direction_4_neurologic_ablate_parallel_submit.sh}"

case "${ARM}" in
  len) METHOD=direction_4_neurologic_thin_len_hl50_B ;;
  lam03) METHOD=direction_4_neurologic_thin_lam03_hl50_B ;;
  group) METHOD=direction_4_neurologic_thin_group_hl50_B ;;
  prefix) METHOD=direction_4_neurologic_thin_prefix_hl50_B ;;
  b4_a50) METHOD=direction_4_neurologic_thin_b4_a50_hl50_B ;;
  b8_a20) METHOD=direction_4_neurologic_thin_b8_a20_hl50_B ;;
  b8_a100) METHOD=direction_4_neurologic_thin_b8_a100_hl50_B ;;
  b16_a50) METHOD=direction_4_neurologic_thin_b16_a50_hl50_B ;;
  b16_a100) METHOD=direction_4_neurologic_thin_b16_a100_hl50_B ;;
  len_lam03) METHOD=direction_4_neurologic_thin_len_lam03_hl50_B ;;
  v2) METHOD=direction_4_neurologic_thin_v2_hl50_B ;;
  *)
    echo "Unknown ARM='${ARM}'" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Missing venv at ${VENV}" >&2
  exit 1
fi

if [[ -f /vol/cuda/12.0.0/setup.sh ]]; then
  # shellcheck disable=SC1091
  source /vol/cuda/12.0.0/setup.sh
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export RESEARCH_DB="${PROJECT}/research/runs/direction_4_smoke5_${ARM}.db"

echo "=== Direction 4 Neurologic arm=${ARM} method=${METHOD} — $(date -Is) ==="
echo "RESEARCH_DB=${RESEARCH_DB}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0
PY

python3 -m research.benchmarks.loader \
  "research/benchmarks/${BENCHMARK}.yaml"

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume

echo "=== Direction 4 arm=${ARM} done $(date -Is) ==="
