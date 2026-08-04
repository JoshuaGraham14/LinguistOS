#!/bin/bash
# Welsh frontier ceiling: GPT-5.5 Fix-B plain on welsh_transfer_n10 (N=10).
# Generation + live EF + cy-v2 naturalness judge. API-bound (GPU unused).
#
# Sanity-check arm: strong model on the same plain prompt as Qwen vanilla,
# so we can see whether EF/judge behave as expected when the model can
# actually produce Welsh.
#
# Usage (from LinguistOS-welsh):
#   sbatch research/scripts/cluster/welsh_frontier_gpt55_plain_n10.sh

#SBATCH --job-name=welsh_gpt55_pl
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --partition=a30
#SBATCH --time=08:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-welsh/logs/welsh_frontier_gpt55_plain_n10_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
METHOD=welsh_frontier_gpt55_plain_n10
BENCHMARK=welsh_transfer_n10
: "${RESUME:=1}"
DB="${PROJECT}/research/runs/welsh_frontier_gpt55_plain_n10.db"
EXPORT="${PROJECT}/research/welsh/manifests/welsh_frontier_gpt55_plain_n10_summary.json"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs" "${PROJECT}/research/welsh/manifests"

# Prefer MAIN .venv (openai + full research deps), fall back to welsh tree.
if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "ERROR: no usable venv" >&2
  exit 1
fi
python3 -c "import openai" || {
  echo "ERROR: openai missing from active venv" >&2
  exit 1
}

cd "${PROJECT}"
export PROJECT
export RESEARCH_DB="${DB}"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
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

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY not set" >&2
  exit 1
fi

echo "=== Welsh frontier GPT-5.5 plain n10 — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  BENCHMARK=${BENCHMARK} METHOD=${METHOD}"
echo "  RESEARCH_DB=${RESEARCH_DB} RESUME=${RESUME}"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION; print('welsh_prompt', WELSH_PROMPT_VERSION)"

RESUME_FLAG=()
if [[ "${RESUME}" != "0" ]]; then
  RESUME_FLAG+=(--resume)
fi

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --with-naturalness-judge \
  --skip-experiment-group-metrics \
  "${RESUME_FLAG[@]}"

echo ""
echo "=== Exporting summary ==="
python3 -m research.scripts.audit_welsh_judge_n10 \
  --db "${RESEARCH_DB}" \
  --out "${EXPORT}"

echo ""
echo "=== Headline ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("research/welsh/manifests/welsh_frontier_gpt55_plain_n10_summary.json")
obj = json.loads(p.read_text())
s = obj.get("summary", obj)
print(f"  n={s.get('n_sentences')} EF={s.get('ef_pass_rate')}")
print(f"  tfu={s.get('target_form_use')}")
print(f"  flags={s.get('flags')}")
print(f"  prompt={s.get('prompt_versions')}")
PY

echo "=== done $(date -Is) ==="
echo "DB: ${RESEARCH_DB}"
echo "Summary: ${EXPORT}"
