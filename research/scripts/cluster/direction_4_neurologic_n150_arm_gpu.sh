#!/bin/bash
# Direction 4 Neurologic n150 arm — one Slurm job = one RESEARCH_DB.
#
# Required env:
#   ARM — thin_B | b16_a50
#
# Usage:
#   bash research/scripts/cluster/direction_4_neurologic_n150_parallel_submit.sh

#SBATCH --job-name=d4_n150
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=48:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_4_n150_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_diagnostic_n150

: "${ARM:?Set ARM (thin_B|b16_a50). Prefer direction_4_neurologic_n150_parallel_submit.sh}"

case "${ARM}" in
  thin_B) METHOD=direction_4_neurologic_thin_n150_B ;;
  b16_a50) METHOD=direction_4_neurologic_thin_b16_a50_n150_B ;;
  inject_b16) METHOD=direction_4_neurologic_thin_inject_b16_a50_n150_B ;;
  *)
    echo "Unknown ARM='${ARM}' (expected thin_B, b16_a50 or inject_b16)" >&2
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
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export RESEARCH_DB="${PROJECT}/research/runs/direction_4_n150_${ARM}.db"

echo "=== Direction 4 Neurologic n150 arm=${ARM} method=${METHOD} — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
echo "BENCHMARK=${BENCHMARK}"
echo "RESEARCH_DB=${RESEARCH_DB}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0
PY

python3 -m research.benchmarks.loader \
  "research/benchmarks/${BENCHMARK}.yaml"

python3 - <<PY
from research.methods.loader import find_method_yaml
path = find_method_yaml("${METHOD}")
assert path is not None, f"Missing method preset: ${METHOD}"
print(f"Method preset OK: {path}")
PY

# Skip O(n^2) experiment-wide group metrics on 4650 sentences (playbook §1).
python3 -m research.run_experiment \
  --benchmark "${BENCHMARK}" \
  --method "${METHOD}" \
  --live \
  --resume \
  --skip-experiment-group-metrics

echo "=== Direction 4 n150 arm=${ARM} done $(date -Is) ==="
