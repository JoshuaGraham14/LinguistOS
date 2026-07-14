#!/bin/bash
# Direction 1.2 Fix-B headline arm on spanish_diagnostic_n150 (150×31=4650).
# One Slurm job = one arm = one RESEARCH_DB (parallel-safe).
#
# Usage (usually via the submit wrapper):
#   sbatch --export=ALL,ARM=vanilla_plain_B \
#     research/scripts/cluster/direction_1p2_n150_B_arm_gpu.sh
#
# Required env:
#   ARM — short arm key (see case below)
# Optional env:
#   HF_BATCH_SIZE — override padded HF batch (defaults set per arm below)
#   INCLUDE_QWEN4B — unused here; 4B has its own ARM key

#SBATCH --job-name=d1p2_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_n150_B_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_diagnostic_n150

: "${ARM:?Set ARM (e.g. vanilla_plain_B). Prefer direction_1p2_n150_B_submit.sh}"

case "${ARM}" in
  vanilla_plain_B)
    METHOD=direction_1_vanilla_plain_n150_B
    DEFAULT_HF_BATCH_SIZE=16
    ;;
  inject_plain_B)
    METHOD=direction_1_inject_plain_n150_B
    DEFAULT_HF_BATCH_SIZE=16
    ;;
  soft_plain_B)
    # Fix B + soft logit bias; num_beams=4 (default soft_B)
    METHOD=direction_1b_soft_plain_n150_B
    DEFAULT_HF_BATCH_SIZE=4
    ;;
  soft_plain_B_beams8)
    METHOD=direction_1b_soft_plain_n150_B_beams8
    DEFAULT_HF_BATCH_SIZE=4
    ;;
  soft_inject_plain_B)
    METHOD=direction_1b_soft_inject_plain_n150_B
    DEFAULT_HF_BATCH_SIZE=4
    ;;
  hard_plain_B)
    METHOD=direction_1a_hard_plain_n150_B
    DEFAULT_HF_BATCH_SIZE=4
    ;;
  soft_plain_B_beams8_qwen4b)
    METHOD=direction_1b_soft_plain_n150_B_beams8_qwen4b
    DEFAULT_HF_BATCH_SIZE=2
    ;;
  *)
    echo "Unknown ARM='${ARM}'" >&2
    echo "Known: vanilla_plain_B inject_plain_B soft_plain_B soft_plain_B_beams8 soft_inject_plain_B hard_plain_B soft_plain_B_beams8_qwen4b" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

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

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/qwen_batch_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export HF_BATCH_SIZE="${HF_BATCH_SIZE:-${DEFAULT_HF_BATCH_SIZE}}"
export RESEARCH_DB="${PROJECT}/research/runs/direction_1p2_n150_${ARM}.db"

echo "=== D1.2 Fix-B n150 arm — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
echo "  ARM=${ARM}"
echo "  method=${METHOD}"
echo "  benchmark=${BENCHMARK}"
echo "  HF_BATCH_SIZE=${HF_BATCH_SIZE}"
echo "  RESEARCH_DB=${RESEARCH_DB}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0, "LanguageTool pre-flight failed"
PY

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

python3 - <<PY
from research.methods.loader import find_method_yaml
path = find_method_yaml("${METHOD}")
assert path is not None, f"Missing method preset: ${METHOD}"
print(f"Method preset OK: {path}")
PY

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume

echo ""
echo "=== D1.2 Fix-B n150 ${ARM} done $(date -Is) ==="
