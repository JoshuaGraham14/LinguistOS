#!/bin/bash
# Re-judge participle cells under LLM-judge prompt v3 (He/haber fix).
#
# Package: 18 LoRA OOD matrix DBs + GPT-5.5 frontier ceiling (~684 calls).
# API-only — no GPU requested. Archives old judge rows; backs up each DB once.
#
# Usage (cluster head node, after git pull on this branch):
#   sbatch research/scripts/cluster/rescore_participle_judge_v3.sh
#   DRY_RUN=1 sbatch research/scripts/cluster/rescore_participle_judge_v3.sh

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

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
else
  echo "ERROR: venv not found at ${VENV}" >&2
  exit 1
fi

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" && "${DRY_RUN}" != "1" ]]; then
  echo "ERROR: OPENAI_API_KEY not set" >&2
  exit 1
fi

echo "=== participle judge v3 rescore — $(date -Is) ==="
echo "  HOST=$(hostname) PROJECT=${PROJECT}"
echo "  git=$(git -C "${PROJECT}" rev-parse --abbrev-ref HEAD) @ $(git -C "${PROJECT}" rev-parse --short HEAD)"
echo "  DRY_RUN=${DRY_RUN}"

ARGS=(--project "${PROJECT}")
if [[ "${DRY_RUN}" == "1" ]]; then
  ARGS+=(--dry-run)
fi

python3 -m research.scripts.rescore_participle_judge_v3 "${ARGS[@]}"
echo "=== done — $(date -Is) ==="
