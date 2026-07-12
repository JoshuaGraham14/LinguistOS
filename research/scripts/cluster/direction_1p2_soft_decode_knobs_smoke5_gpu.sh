#!/bin/bash
# Direction 1.2 — Track 1: decode-knob ablation on top of Fix B.
# RP = no_repeat_ngram_size=3, MT = min_new_tokens=6, LP = length_penalty=1.5,
# ALL = RP+MT+LP. Applied to soft_plain_B and soft_inject_plain_B.
#
# Usage: sbatch research/scripts/cluster/direction_1p2_soft_decode_knobs_smoke5_gpu.sh

#SBATCH --job-name=d1p2_knobs
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=02:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_soft_decode_knobs_smoke5_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

ARMS=(
  "soft_plain_B_RP:direction_1b_soft_plain_hl50_B_RP"
  "soft_plain_B_MT:direction_1b_soft_plain_hl50_B_MT"
  "soft_plain_B_LP:direction_1b_soft_plain_hl50_B_LP"
  "soft_plain_B_ALL:direction_1b_soft_plain_hl50_B_ALL"
  "soft_inject_plain_B_RP:direction_1b_soft_inject_plain_hl50_B_RP"
  "soft_inject_plain_B_MT:direction_1b_soft_inject_plain_hl50_B_MT"
  "soft_inject_plain_B_LP:direction_1b_soft_inject_plain_hl50_B_LP"
  "soft_inject_plain_B_ALL:direction_1b_soft_inject_plain_hl50_B_ALL"
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

echo "=== D1.2 Track1 decode knobs (8 arms × 155) — $(date -Is) ==="
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
echo "=== D1.2 Track1 decode knobs done $(date -Is) ==="
