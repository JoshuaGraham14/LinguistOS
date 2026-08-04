#!/bin/bash
# Shared body for welsh_frontier_gpt55_{plain,inject}_n150.sh (sourced).
set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
: "${ARM:=plain}"   # plain | inject
: "${RESUME:=1}"
BENCHMARK=welsh_transfer_n150

case "${ARM}" in
  plain)
    METHOD=welsh_frontier_gpt55_plain_n150
    DB="${PROJECT}/research/runs/welsh_frontier_gpt55_plain_n150.db"
    EXPORT="${PROJECT}/research/welsh/manifests/welsh_frontier_gpt55_plain_n150_summary.json"
    ;;
  inject)
    METHOD=welsh_frontier_gpt55_inject_n150
    DB="${PROJECT}/research/runs/welsh_frontier_gpt55_inject_n150.db"
    EXPORT="${PROJECT}/research/welsh/manifests/welsh_frontier_gpt55_inject_n150_summary.json"
    ;;
  *)
    echo "ERROR: ARM must be plain or inject (got ${ARM})" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs" "${PROJECT}/research/welsh/manifests"

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

if [[ ! -f "${PROJECT}/research/benchmarks/${BENCHMARK}.yaml" ]]; then
  echo "ERROR: missing benchmark ${PROJECT}/research/benchmarks/${BENCHMARK}.yaml" >&2
  exit 1
fi

echo "=== Welsh frontier GPT-5.5 ${ARM} n150 — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  BENCHMARK=${BENCHMARK} METHOD=${METHOD} ARM=${ARM}"
echo "  RESEARCH_DB=${RESEARCH_DB} RESUME=${RESUME}"
python3 -c "from research.evaluation.sentence.naturalness_llm_judge import WELSH_PROMPT_VERSION; print('welsh_prompt', WELSH_PROMPT_VERSION)"
python3 -c "from research.generation import GENERATOR_REGISTRY; print('inject_gen', 'baseline_gpt_form_injected_plain_b' in GENERATOR_REGISTRY)"

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
EXPORT_PATH="${EXPORT}" python3 - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["EXPORT_PATH"])
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
