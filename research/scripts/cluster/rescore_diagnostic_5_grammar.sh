#!/bin/bash
#SBATCH --job-name=d5_grammar_rescore
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --partition=a30
#SBATCH --time=04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/diagnostic_5_grammar_rescore_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
RUNS_DIR="${PROJECT}/research/runs"

mkdir -p "${PROJECT}/logs"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
else
  echo "Missing venv at ${VENV}" >&2
  exit 1
fi

cd "${PROJECT}"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"

echo "=== Diagnostic 5 grammar rescore — $(date -Is) ==="
echo "LTP_PATH=${LTP_PATH}"
echo "Host: $(hostname)"
echo "Job: ${SLURM_JOB_ID:-interactive}"

# Sanity: LanguageTool must initialize (no disk quota / Java errors)
python3 -c "
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
ev = LanguageToolGrammarEvaluator()
r = ev.evaluate('Yo como manzanas.', 'I eat apples.', {'target_language': 'es'})
assert r.score == 1.0, r.details
print('LanguageTool OK:', r.details.get('match_count', 0), 'matches')
"

for arm in 5a 5b 5c; do
  db="${RUNS_DIR}/diagnostic_${arm}.db"
  if [[ ! -f "${db}" ]]; then
    echo "SKIP ${arm}: missing ${db}"
    continue
  fi
  echo ""
  echo "--- Rescoring ${arm} ---"
  export RESEARCH_DB="${db}"
  python3 -m research.scripts.rescore_diagnostic_5_grammar --arm "${arm}"
done

echo ""
echo "=== Done $(date -Is) ==="
echo "Re-merge if needed: bash research/scripts/cluster/diagnostic_5_merge.sh"
