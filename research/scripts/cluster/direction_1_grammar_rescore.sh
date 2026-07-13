#!/bin/bash
# Direction 1.2 — grammar-only rescore across per-arm DBs (no regeneration).
# Use if the first pass came back grammar_languagetool=0 everywhere.
#
# Usage: sbatch research/scripts/cluster/direction_1_grammar_rescore.sh

#SBATCH --job-name=d1p2_gramm
#SBATCH --gres=gpu:0
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/direction_1p2_grammar_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"

ARMS=(
  vanilla_plain
  inject_plain
  hard_plain
  hard_inject_plain
  soft_plain
)

mkdir -p "${PROJECT}/logs"

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

cd "${PROJECT}"
export PROJECT
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Direction 1.2 grammar rescore — $(date -Is) ==="

# Pre-flight
python3 - <<'PY'
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate("Yo como manzanas.", "I eat apples.", {"target_language": "es"})
print(f"LT pre-flight: score={r.score}")
assert r.score == 1.0, "LanguageTool pre-flight failed — check LTP_PATH and Java"
PY

for ARM in "${ARMS[@]}"; do
  DB_PATH="${PROJECT}/research/runs/direction_1p2_${ARM}.db"
  if [[ ! -f "${DB_PATH}" ]]; then
    echo "  Skip ${ARM}: ${DB_PATH} not found"
    continue
  fi
  echo ""
  echo "=== rescore ${ARM} — $(date -Is) ==="
  python3 -m research.scripts.rescore_direction_1_grammar --arm "${ARM}" --db "${DB_PATH}"
done

echo ""
echo "=== Direction 1.2 grammar rescore done $(date -Is) ==="
