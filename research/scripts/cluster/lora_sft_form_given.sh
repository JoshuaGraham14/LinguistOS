#!/bin/bash
# Build LoRA-form SFT JSONL (Experiment A) from scored n150 DBs, then train
# Qwen3-1.7B LoRA. Train prompts are Fix-B inject (gold surface form given).
#
# Usage:
#   sbatch research/scripts/cluster/lora_sft_form_given.sh

#SBATCH --job-name=lora_form
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_sft_form_given_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs/lora"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
elif [[ -f /vol/bitbucket/jjg25/myvenv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /vol/bitbucket/jjg25/myvenv/bin/activate
else
  echo "No venv found" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false

echo "=== Installing LoRA train deps if needed ==="
python - <<'PY'
import importlib.util
need = []
for pkg in ("peft", "trl", "datasets"):
    if importlib.util.find_spec(pkg) is None:
        need.append(pkg)
if need:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *need])
    print("installed", need)
else:
    print("deps ok")
PY

# Canonical LoRA-form paths; legacy form_given tree holds the published A adapter
DATA="${PROJECT}/research/runs/lora/sft_lora_form_n150.jsonl"
OUT="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_form"
LEGACY_OUT="${PROJECT}/research/runs/lora/qwen3_1p7b_form_given"

echo "=== Building SFT dataset (LoRA-form) ==="
python -m research.scripts.build_lora_sft_dataset \
  --experiment lora-form \
  --runs-dir "${PROJECT}/research/runs" \
  --output "${DATA}"

echo "=== Training LoRA-form ==="
python -m research.scripts.train_lora_sft \
  --data "${DATA}" \
  --output-dir "${OUT}" \
  --model Qwen/Qwen3-1.7B \
  --epochs 3 \
  --batch-size 4 \
  --grad-accum 4

echo "=== Done ==="
ls -lh "${OUT}" | head
if [[ -d "${LEGACY_OUT}" ]]; then
  echo "(legacy LoRA-form adapter still at ${LEGACY_OUT})"
fi
