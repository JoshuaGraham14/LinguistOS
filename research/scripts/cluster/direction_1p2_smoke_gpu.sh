#!/bin/bash
# Direction 1.2 — 2-verb smoke on spanish_direction_hl50_smoke.
# Same runner as the full sequential D1.2 job, but points at the 2-verb
# smoke benchmark (62 cells vs 1,550 full). Wall time: ~20–40 min for all
# five arms depending on model-load / LT init overhead.
#
# Usage: sbatch research/scripts/cluster/direction_1p2_smoke_gpu.sh

#SBATCH --job-name=d1p2_smoke
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=01:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_smoke_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
BENCHMARK=spanish_direction_hl50_smoke

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

echo "=== Direction 1.2 SMOKE (5 arms × 62 cells) — $(date -Is) ==="
echo "Host: $(hostname)  Job: ${SLURM_JOB_ID:-interactive}"
nvidia-smi || true

# Phase 0 (a): LT pre-flight — abort the whole job if LanguageTool cannot init.
python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score} details_keys={sorted(r.details.keys())}")
assert r.score == 1.0, "LanguageTool pre-flight failed — check LTP_PATH and Java"
PY

# Phase 0 (b): tokenisation sanity on the smoke benchmark.
python3 -m research.scripts.inspect_force_variants \
  --benchmark "research/benchmarks/${BENCHMARK}.yaml" \
  --model Qwen/Qwen3-1.7B --summary

python3 -m research.benchmarks.loader "research/benchmarks/${BENCHMARK}.yaml"

for ENTRY in "${ARMS[@]}"; do
  ARM="${ENTRY%%:*}"
  METHOD="${ENTRY##*:}"
  DB_PATH="${PROJECT}/research/runs/direction_1p2_smoke_${ARM}.db"
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
echo "=== Direction 1.2 smoke done $(date -Is) ==="
