#!/bin/bash
# Direction 1.2 recommended arm on Qwen3-4B — full hl50.
# Method: soft_plain_B (Fix B sentence prompt) + num_beams=8, no form injection.
#
# Usage: sbatch research/scripts/cluster/direction_1p2_soft_plain_B_beams8_qwen4b_hl50_gpu.sh

#SBATCH --job-name=d1p2_sp_4b
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_soft_plain_B_beams8_qwen4b_hl50_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50
METHOD=direction_1b_soft_plain_hl50_B_beams8_qwen4b
ARM=soft_plain_B_beams8_qwen4b

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
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export RESEARCH_DB="${PROJECT}/research/runs/direction_1p2_hl50_${ARM}.db"

echo "=== D1.2 recommended arm on Qwen3-4B (full hl50) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
echo "  method=${METHOD}"
echo "  benchmark=${BENCHMARK}"
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

python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume

echo ""
echo "=== D1.2 soft_plain_B beams8 Qwen3-4B hl50 done $(date -Is) ==="
