#!/bin/bash
# Rescore Welsh n10 audit DBs: mutation-aware EF + LLM judge (cy-v2).
# No regeneration — OpenAI used only for the judge arm.
#
# Usage (from LinguistOS-welsh):
#   sbatch research/scripts/cluster/welsh_n10_rescore_ef_judge.sh

#SBATCH --job-name=welsh_n10_resc
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_n10_rescore_ef_judge_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
: "${EVALUATOR:=both}"
: "${RESUME:=0}"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/welsh/manifests"

if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "Missing venv" >&2
  exit 1
fi

cd "${PROJECT}"
export PROJECT
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "${PROJECT}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/research/.env"
  set +a
elif [[ -f "${MAIN}/research/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${MAIN}/research/.env"
  set +a
fi

if [[ "${EVALUATOR}" != "ef" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY required for judge rescore" >&2
  exit 1
fi

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

echo "=== Welsh n10 EF+judge rescore — $(date -Is) ==="
echo "  EVALUATOR=${EVALUATOR} RESUME=${RESUME}"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION; print('welsh_prompt', WELSH_PROMPT_VERSION)"
python3 -c "from research.welsh.mutation import mutation_policy_for_constraints; print('mut_policy_past', mutation_policy_for_constraints({'construction':'periphrastic','tense':'past'}))"

python3 -m research.scripts.rescore_welsh_n10_ef_judge \
  --runs-dir "${PROJECT}/research/runs" \
  --export-dir "${PROJECT}/research/welsh/manifests" \
  --evaluator "${EVALUATOR}" \
  --judge-commit-every 25 \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Headline EF after rescore ==="
python3 - <<'PY'
import json
from pathlib import Path
for key in ("plain", "fewshot", "inject"):
    p = Path(f"research/welsh/manifests/welsh_judge_audit_{key}_rescored_summary.json")
    if not p.is_file():
        print(key, "missing")
        continue
    obj = json.loads(p.read_text())
    sm = obj.get("summary", obj)
    print(
        f"{key}: EF={sm.get('ef_pass_rate')} "
        f"tfu={sm.get('target_form_use')} "
        f"prompt={sm.get('prompt_versions')}"
    )
PY

echo "=== done $(date -Is) ==="
