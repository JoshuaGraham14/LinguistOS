#!/bin/bash
# Score the 15-pair naturalness validation set with the perplexity and/or
# judge evaluators. Writes raw.jsonl, summary.json, and report.md into
# research/runs/naturalness_validation/<tag>/.
#
# Exit code: 0 if the promotion gate passes, 2 otherwise. Use this as a
# pre-flight before running the full direction_1_naturalness_rescore.sh.
#
# Usage: sbatch research/scripts/cluster/naturalness_validation.sh
# Overrides: EVALUATOR=perplexity|judge|both  TAG=<subdir>

#SBATCH --job-name=natural_val
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=01:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/naturalness_validation_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"

: "${EVALUATOR:=both}"
: "${TAG:=$(date -u +%Y%m%dT%H%M%SZ)}"

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

# Load research/.env into the shell so the bash preflight and Python both see
# OPENAI_API_KEY (Python also load_dotenv's, but we fail fast here).
if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
fi

echo "=== Naturalness validation — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR}"
echo "  TAG=${TAG}"

if [[ "${EVALUATOR}" == "judge" || "${EVALUATOR}" == "both" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "  ERROR: OPENAI_API_KEY not set — judge cannot run." >&2
    echo "  Put it in ${PROJECT}/research/.env (rsync'd from Mac) or export it before sbatch." >&2
    exit 1
  fi
fi

# `|| GATE_EXIT=$?` keeps `set -e` from killing the script on a gate FAIL
# (exit 2) so the summary line below still prints.
GATE_EXIT=0
python3 -m research.scripts.run_naturalness_validation \
  --evaluator "${EVALUATOR}" \
  --tag "${TAG}" || GATE_EXIT=$?

echo ""
echo "=== Validation done — $(date -Is) (exit=${GATE_EXIT}) ==="
exit "${GATE_EXIT}"
