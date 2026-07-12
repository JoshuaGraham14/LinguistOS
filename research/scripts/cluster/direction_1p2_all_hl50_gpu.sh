#!/bin/bash
# Direction 1.2 pilot — sequential, one GPU, per-arm DB.
# Runs the D1.2 arm set on `spanish_direction_hl50`:
#   1) vanilla-plain      (baseline_hf_plain, no inject, no beam)  ← control
#   2) inject-plain       (form injected in prompt, greedy T=0)
#   3) hard-plain         (beam + force_words_ids, no inject)
#   4) hard-inject-plain  (beam + force_words_ids + inject in prompt)
#   5) soft-plain         (beam + logit bias, no inject)
#
# Each arm writes to its own per-arm DB under research/runs/ (playbook §0).
# The cluster env script (research_cache_env.sh) sets LTP_PATH on the project
# volume so LanguageTool works (D5 lesson).
#
# Usage: sbatch research/scripts/cluster/direction_1p2_all_hl50_gpu.sh

#SBATCH --job-name=d1p2_all
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=24:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_all_hl50_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50

# arm_name : method_yaml_name
ARMS=(
  "vanilla_plain:direction_1_vanilla_plain_hl50"
  "inject_plain:direction_1_inject_plain_hl50"
  "hard_plain:direction_1a_hard_plain_hl50"
  "hard_inject_plain:direction_1a_hard_inject_plain_hl50"
  "soft_plain:direction_1b_soft_plain_hl50"
)

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "Create venv: python3 -m venv ${VENV} && pip install -r research/requirements.txt torch transformers accelerate" >&2
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

echo "=== Direction 1.2 pilot (5 arms) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

# Pre-flight: verify LanguageTool init before running any arm.
python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score} details_keys={sorted(r.details.keys())}")
assert r.score == 1.0, "LanguageTool pre-flight failed — check LTP_PATH and Java"
PY

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

for ENTRY in "${ARMS[@]}"; do
  ARM="${ENTRY%%:*}"
  METHOD="${ENTRY##*:}"
  DB_PATH="${PROJECT}/research/runs/direction_1p2_${ARM}.db"
  export RESEARCH_DB="${DB_PATH}"
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
echo "=== Direction 1.2 arms done $(date -Is) ==="
