#!/bin/bash
# Minimal naturalness rescore for frontier GPT-5.5 OOD (gen-style header).
# Does not depend on Slurm propagating SSH env.

#SBATCH --job-name=gpt55_ood_nat
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --partition=a30
#SBATCH --time=06:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55/logs/frontier_ceiling_gpt55_ood_nat_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-frontier-gpt55
MAIN=/vol/bitbucket/jjg25/LinguistOS
DB_PATH="${PROJECT}/research/runs/frontier_ceiling_gpt55_vanilla_ood_n36.db"
METHOD_NAME=frontier_ceiling_gpt55_vanilla_ood_n36
LABEL=frontier_ceiling_gpt55_vanilla_ood_n36

mkdir -p "${PROJECT}/logs"
cd "${PROJECT}"

# shellcheck disable=SC1091
source "${MAIN}/.venv/bin/activate"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"

# Reuse MAIN caches for Salamandra / LanguageTool
if [[ -d "${MAIN}/.cache/huggingface" ]]; then
  export HF_HOME="${MAIN}/.cache/huggingface"
  export TRANSFORMERS_CACHE="${HF_HOME}"
fi
if [[ -d "${MAIN}/.cache/language_tool_python" ]]; then
  export LTP_PATH="${MAIN}/.cache/language_tool_python"
fi

export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

set -a
# shellcheck disable=SC1091
source "${PROJECT}/research/.env"
set +a

: "${OPENAI_API_KEY:?OPENAI_API_KEY missing}"
test -f "${DB_PATH}"

echo "=== Frontier ceiling GPT-5.5 OOD naturalness — $(date -Is) ==="
echo "  DB=${DB_PATH}"
echo "  HOST=$(hostname) CUDA=${CUDA_VISIBLE_DEVICES:-unset}"
nvidia-smi || true

python -c "import wordfreq, openai, torch; print('deps_ok', torch.cuda.is_available())"

export DB_PATH METHOD_NAME LABEL
python - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from research.scripts.rescore_direction_1_naturalness import _run_one

_run_one(
    label=os.environ["LABEL"],
    method_name=os.environ["METHOD_NAME"],
    db_path=Path(os.environ["DB_PATH"]),
    experiment_id=None,
    which="both",
    ppl_commit_every=200,
    judge_commit_every=50,
    resume=True,
    dry_run=False,
)
print("=== naturalness done ===")
PY
