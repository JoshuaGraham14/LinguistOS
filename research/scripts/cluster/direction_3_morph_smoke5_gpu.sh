#!/bin/bash
# Direction 3 — morphology-aware constrained decoding (8 arms × 155 cells).
#
# Usage:
#   sbatch research/scripts/cluster/direction_3_morph_smoke5_gpu.sh

#SBATCH --job-name=d3_morph
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_3_morph_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke5

ARMS=(
  "morph_ban_B:direction_1c_morph_ban_hl50_B"
  "morph_ban_inject_B:direction_1c_morph_ban_inject_hl50_B"
  "hard_morph_B:direction_1c_hard_morph_hl50_B"
  "hard_morph_inject_B:direction_1c_hard_morph_inject_hl50_B"
  "soft_morph_B:direction_1c_soft_morph_hl50_B"
  "soft_morph_inject_B:direction_1c_soft_morph_inject_hl50_B"
  "soft_morph_forms_B:direction_1c_soft_morph_forms_hl50_B"
  "soft_morph_pron_B:direction_1c_soft_morph_pron_hl50_B"
)

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

echo "=== Direction 3 morph-aware smoke5 (8 arms × 155) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0
PY

python3 -m research.scripts.audit_morph_ban_homonyms \
  --benchmark "research/benchmarks/${BENCHMARK}.yaml"
python3 -m research.benchmarks.loader \
  "research/benchmarks/${BENCHMARK}.yaml"

for ENTRY in "${ARMS[@]}"; do
  ARM="${ENTRY%%:*}"
  METHOD="${ENTRY##*:}"
  export RESEARCH_DB="${PROJECT}/research/runs/direction_3_smoke5_${ARM}.db"
  echo ""
  echo "=== ${METHOD} (arm=${ARM}) — $(date -Is) ==="
  echo "    RESEARCH_DB=${RESEARCH_DB}"
  python3 -m research.run_experiment \
    --benchmark "${BENCHMARK}" \
    --method "${METHOD}" \
    --live \
    --resume
done

echo ""
echo "=== Direction 3 generation done $(date -Is) ==="
