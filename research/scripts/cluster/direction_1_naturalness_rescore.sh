#!/bin/bash
# Direction 1.2 — naturalness rescore for the headline smoke5 Form/LT table.
# Runs fluency_perplexity (Salamandra-2b, BF16, CUDA) and, when
# OPENAI_API_KEY is present, naturalness_llm_judge (gpt-5.4-mini).
#
# Default: --preset headline_smoke5 (7 locked arms / ~992 sentences).
# Override: PRESET=  ARMS=...  for legacy per-arm mode, or EVALUATOR=perplexity|judge|both
#
# Usage: sbatch research/scripts/cluster/direction_1_naturalness_rescore.sh

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
: "${PRESET:=headline_smoke5}"
: "${RESUME:=1}"

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

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

echo "=== Direction 1.2 naturalness rescore — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR}"
echo "  PRESET=${PRESET}"
echo "  RESUME=${RESUME}"

# Pre-flight: import both evaluators.
python3 - <<'PY'
from research.evaluation.sentence.fluency_perplexity import FluencyPerplexityEvaluator
from research.evaluation.sentence.naturalness_llm_judge import NaturalnessLlmJudgeEvaluator
print(f"OK: {FluencyPerplexityEvaluator().name} + {NaturalnessLlmJudgeEvaluator().name}")
PY

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "  ERROR: OPENAI_API_KEY not set — judge cannot run." >&2
    echo "  Put it in ${PROJECT}/research/.env or export it before sbatch." >&2
    exit 1
  fi
fi

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG=(--resume)
fi

if [[ -n "${PRESET}" ]]; then
  # Dry-run first so a missing/empty DB fails before spending API calls.
  python3 -m research.scripts.rescore_direction_1_naturalness \
    --preset "${PRESET}" \
    --evaluator "${EVALUATOR}" \
    --dry-run
  echo ""
  echo "=== dry-run OK — starting live rescore ==="
  python3 -m research.scripts.rescore_direction_1_naturalness \
    --preset "${PRESET}" \
    --evaluator "${EVALUATOR}" \
    "${RESUME_FLAG[@]}"
else
  # Legacy mode: iterate ARMS against direction_1p2_<arm>.db
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
  echo "  ARMS=${ARMS[*]}"
  for ARM in "${ARMS[@]}"; do
    DB_PATH="${PROJECT}/research/runs/direction_1p2_${ARM}.db"
    if [[ ! -f "${DB_PATH}" ]]; then
      echo "  Skip ${ARM}: ${DB_PATH} not found"
      continue
    fi
    echo ""
    echo "=== rescore ${ARM} — $(date -Is) ==="
    python3 -m research.scripts.rescore_direction_1_naturalness \
      --arm "${ARM}" --db "${DB_PATH}" --evaluator "${EVALUATOR}" \
      "${RESUME_FLAG[@]}"
  done
fi

echo ""
echo "=== Direction 1.2 naturalness rescore done $(date -Is) ==="
