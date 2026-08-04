#!/bin/bash
# Few-shot OOD n36 generation (static or dynamic) on Qwen3-1.7B.
#
# Env:
#   ARM = static | dynamic
#   RESEARCH_DB = absolute output db path
#
# Usage:
#   ARM=static RESEARCH_DB=/vol/bitbucket/jjg25/LinguistOS/research/runs/fewshot_ood_n36_static.db \
#     sbatch research/scripts/cluster/fewshot_ood_n36_eval_arm.sh

#SBATCH --job-name=fewshot_ood
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/fewshot_ood_n36_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

: "${ARM:?Set ARM=static|dynamic}"
: "${RESEARCH_DB:?Set RESEARCH_DB path}"

case "${ARM}" in
  static) METHOD=direction_5_fewshot_static_k3_ood_n36 ;;
  dynamic) METHOD=direction_5_fewshot_dynamic_k3_ood_n36 ;;
  *) echo "Unknown ARM=${ARM}" >&2; exit 1 ;;
esac

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

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export HF_BATCH_SIZE="${HF_BATCH_SIZE:-16}"

mkdir -p "$(dirname "${RESEARCH_DB}")" "${PROJECT}/logs"
export RESEARCH_DB

echo "=== Few-shot OOD n36 generation — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
echo "ARM=${ARM} METHOD=${METHOD} DB=${RESEARCH_DB}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0
PY

python3 -m research.benchmarks.loader \
  "research/benchmarks/spanish_lora_ood_n36.yaml"

python3 -m research.run_experiment \
  --benchmark spanish_lora_ood_n36 \
  --method "${METHOD}" \
  --live \
  --resume \
  --skip-experiment-group-metrics

echo "Done → ${RESEARCH_DB}"
