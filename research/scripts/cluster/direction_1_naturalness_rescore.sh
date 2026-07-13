#!/bin/bash
# Direction 1.2 — naturalness rescore across per-arm DBs (no regeneration).
# Runs fluency_perplexity (Salamandra-2b, BF16, CUDA) and, when
# OPENAI_API_KEY is present, naturalness_llm_judge (gpt-5.5-mini).
#
# Usage: sbatch research/scripts/cluster/direction_1_naturalness_rescore.sh
# Set EVALUATOR=perplexity|judge|both  (default: both)
# Set ARMS to override the arm list.

#SBATCH --job-name=d1p2_natural
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_natural_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"

: "${EVALUATOR:=both}"
DEFAULT_ARMS=(
  vanilla_plain
  inject_plain
  hard_plain
  hard_inject_plain
  soft_plain
)
if [[ -z "${ARMS:-}" ]]; then
  ARMS=("${DEFAULT_ARMS[@]}")
else
  # shellcheck disable=SC2206
  ARMS=(${ARMS})
fi

mkdir -p "${PROJECT}/logs"

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

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Direction 1.2 naturalness rescore — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR}"
echo "  ARMS=${ARMS[*]}"

# Pre-flight: import both evaluators.
python3 - <<'PY'
from research.evaluation.sentence.fluency_perplexity import FluencyPerplexityEvaluator
from research.evaluation.sentence.naturalness_llm_judge import NaturalnessLlmJudgeEvaluator
print(f"OK: {FluencyPerplexityEvaluator().name} + {NaturalnessLlmJudgeEvaluator().name}")
PY

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "  WARNING: OPENAI_API_KEY not set — judge rescore will be skipped per-arm." >&2
  fi
fi

for ARM in "${ARMS[@]}"; do
  DB_PATH="${PROJECT}/research/runs/direction_1p2_${ARM}.db"
  if [[ ! -f "${DB_PATH}" ]]; then
    echo "  Skip ${ARM}: ${DB_PATH} not found"
    continue
  fi
  echo ""
  echo "=== rescore ${ARM} — $(date -Is) ==="
  python3 -m research.scripts.rescore_direction_1_naturalness \
    --arm "${ARM}" --db "${DB_PATH}" --evaluator "${EVALUATOR}"
done

echo ""
echo "=== Direction 1.2 naturalness rescore done $(date -Is) ==="
