#!/bin/bash
# Direction 1.2 — 5-verb smoke on spanish_direction_hl50_smoke5.
# Runs the full six-arm grid including the new soft_inject_plain combo,
# so we can see whether soft+inject closes the coverage gap without
# regressing to hard-style paradigm dumps.
#
# Usage: sbatch research/scripts/cluster/direction_1p2_smoke5_gpu.sh

#SBATCH --job-name=d1p2_smoke5
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_smoke5_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

ARMS=(
  "vanilla_plain:direction_1_vanilla_plain_hl50"
  "inject_plain:direction_1_inject_plain_hl50"
  "hard_plain:direction_1a_hard_plain_hl50"
  "hard_inject_plain:direction_1a_hard_inject_plain_hl50"
  "soft_plain:direction_1b_soft_plain_hl50"
  "soft_inject_plain:direction_1b_soft_inject_plain_hl50"
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

echo "=== Direction 1.2 SMOKE5 (6 arms × 155 cells) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

# LT pre-flight — abort whole job if LanguageTool cannot init.
python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0, "LanguageTool pre-flight failed"
PY

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

for ENTRY in "${ARMS[@]}"; do
  ARM="${ENTRY%%:*}"
  METHOD="${ENTRY##*:}"
  DB_PATH="${PROJECT}/research/runs/direction_1p2_smoke5_${ARM}.db"
  export RESEARCH_DB="${DB_PATH}"
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
echo "=== Direction 1.2 smoke5 done $(date -Is) ==="
