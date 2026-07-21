#!/bin/bash
# Direction 4 — Neurologic-inspired thin morph CNF search (2 arms × smoke5).
#
# Usage:
#   sbatch research/scripts/cluster/direction_4_neurologic_smoke5_gpu.sh

#SBATCH --job-name=d4_neuro
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_neurologic_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

ARMS=(
  "neurologic_thin_B:direction_4_neurologic_thin_hl50_B"
  "neurologic_thin_inject_B:direction_4_neurologic_thin_inject_hl50_B"
)

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

echo "=== Direction 4 Neurologic smoke5 (2 arms × 155) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
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

for ENTRY in "${ARMS[@]}"; do
  ARM="${ENTRY%%:*}"
  METHOD="${ENTRY##*:}"
  export RESEARCH_DB="${PROJECT}/research/runs/direction_4_smoke5_${ARM}.db"
  echo ""
  echo "=== ${METHOD} (arm=${ARM}) — $(date -Is) ==="
  echo "    RESEARCH_DB=${RESEARCH_DB}"
  python3 -m research.run_experiment \
    --benchmark "${BENCHMARK}" \
    --method "${METHOD}" \
    --live \
    --resume
done

echo ""
echo "=== Direction 4 generation done $(date -Is) ==="
