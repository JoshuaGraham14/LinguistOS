#!/bin/bash
# Direction 1.2 — Fix A × Fix B ablation grid for the two soft arms.
# Six new experiments on the existing 5-verb smoke benchmark. Baselines
# (soft_plain, soft_inject_plain) are reused from the earlier smoke5 run.
#
# Fix A: disable soft bias once the target token sequence has appeared in
#        the beam's tail (LogitsProcessor change).
# Fix B: add an explicit "write a 2–5 word Spanish sentence with the target
#        as main verb, do not output the form alone" instruction to the
#        prompt (subject pronouns don't count).
#
# Usage: sbatch research/scripts/cluster/direction_1p2_soft_fixes_smoke5_gpu.sh

#SBATCH --job-name=d1p2_fixes
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=01:30:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_soft_fixes_smoke5_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

ARMS=(
  "soft_plain_A:direction_1b_soft_plain_hl50_A"
  "soft_plain_B:direction_1b_soft_plain_hl50_B"
  "soft_plain_AB:direction_1b_soft_plain_hl50_AB"
  "soft_inject_plain_A:direction_1b_soft_inject_plain_hl50_A"
  "soft_inject_plain_B:direction_1b_soft_inject_plain_hl50_B"
  "soft_inject_plain_AB:direction_1b_soft_inject_plain_hl50_AB"
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

echo "=== D1.2 soft fixes ablation (6 arms × 155 cells) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0
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
echo "=== D1.2 soft fixes ablation done $(date -Is) ==="
