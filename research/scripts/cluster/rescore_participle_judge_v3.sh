#!/bin/bash
# Re-judge participle cells under LLM-judge prompt v3 (He/haber fix).
#
# Package: 18 LoRA OOD matrix DBs + GPT-5.5 frontier ceiling (~684 calls).
# API-only — no GPU requested. Archives old judge rows; backs up each DB once.
#
# Code lives in LinguistOS-participle-v3 (rsync sidecar); DBs stay under
# LinguistOS/research/runs and LinguistOS-frontier-gpt55 (never rsynced).
#
# Usage (cluster head node):
#   sbatch /vol/bitbucket/jjg25/LinguistOS-participle-v3/research/scripts/cluster/rescore_participle_judge_v3.sh

#SBATCH --job-name=part_v3_judge
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --partition=long
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --export=NONE
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/rescore_participle_judge_v3_%j.out

set -euo pipefail

CODE=/vol/bitbucket/jjg25/LinguistOS-participle-v3
DB_PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${DB_PROJECT}/.venv"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "${DB_PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
else
  echo "ERROR: venv not found at ${VENV}" >&2
  exit 1
fi

cd "${CODE}"
export PROJECT="${DB_PROJECT}"
# shellcheck disable=SC1091
source "${DB_PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${CODE}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${DB_PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${DB_PROJECT}/research/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" && "${DRY_RUN}" != "1" ]]; then
  echo "ERROR: OPENAI_API_KEY not set" >&2
  exit 1
fi

echo "=== participle judge v3 rescore — $(date -Is) ==="
echo "  HOST=$(hostname)"
echo "  CODE=${CODE}"
echo "  DB_PROJECT=${DB_PROJECT}"
echo "  DRY_RUN=${DRY_RUN}"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import PROMPT_VERSION; print('  prompt_version=', PROMPT_VERSION)"

ARGS=(--project "${DB_PROJECT}")
if [[ "${DRY_RUN}" == "1" ]]; then
  ARGS+=(--dry-run)
fi

python3 -m research.scripts.rescore_participle_judge_v3 "${ARGS[@]}"
echo "=== done — $(date -Is) ==="
