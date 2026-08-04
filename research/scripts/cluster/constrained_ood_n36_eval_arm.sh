#!/bin/bash
# Constrained-decoding OOD n36 generation (hard / soft bias / 4B arms).
#
# Env:
#   ARM = hard | hard_best | bias2 | bias8 | bias12 | vanilla_4b | soft_4b
#   RESEARCH_DB = absolute output db path
#
# Usage:
#   ARM=hard RESEARCH_DB=/vol/bitbucket/jjg25/LinguistOS/research/runs/d1_ood_hard.db \
#     sbatch research/scripts/cluster/constrained_ood_n36_eval_arm.sh

#SBATCH --job-name=d1_ood
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/constrained_ood_n36_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

: "${ARM:?Set ARM=hard|hard_best|bias2|bias8|bias12|vanilla_4b|soft_4b}"
: "${RESEARCH_DB:?Set RESEARCH_DB path}"

case "${ARM}" in
  hard)
    METHOD=direction_1a_hard_plain_ood_n36
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}"
    ;;
  hard_best)
    METHOD=direction_1a_hard_plain_best_ood_n36
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}"
    ;;
  bias2)
    METHOD=direction_1b_soft_plain_ood_n36_bias2
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}"
    ;;
  bias8)
    METHOD=direction_1b_soft_plain_ood_n36_bias8
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}"
    ;;
  bias12)
    METHOD=direction_1b_soft_plain_ood_n36_bias12
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-4}"
    ;;
  vanilla_4b)
    METHOD=direction_1_vanilla_plain_ood_n36_qwen4b
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-8}"
    ;;
  soft_4b)
    METHOD=direction_1b_soft_plain_ood_n36_qwen4b
    HF_BATCH_SIZE="${HF_BATCH_SIZE:-1}"
    ;;
  *)
    echo "Unknown ARM=${ARM}" >&2
    exit 1
    ;;
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
export HF_BATCH_SIZE

mkdir -p "$(dirname "${RESEARCH_DB}")" "${PROJECT}/logs"
export RESEARCH_DB

echo "=== Constrained OOD n36 generation — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
echo "ARM=${ARM} METHOD=${METHOD} DB=${RESEARCH_DB} HF_BATCH_SIZE=${HF_BATCH_SIZE}"
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
