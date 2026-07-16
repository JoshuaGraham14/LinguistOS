#!/bin/bash
# Build LoRA-no-inject SFT JSONL (Experiment B) from scored n150 DBs, then train
# Qwen3-1.7B LoRA. Train prompts are Fix-B vanilla/soft text (no gold form).
#
# Usage:
#   sbatch research/scripts/cluster/lora_sft_no_inject.sh

#SBATCH --job-name=lora_no_inj
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_sft_no_inject_%j.out

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

DATA="${PROJECT}/research/runs/lora/sft_lora_no_inject_n150.jsonl"
OUT="${PROJECT}/research/runs/lora/qwen3_1p7b_lora_no_inject"

echo "=== Building SFT dataset (LoRA-no-inject) ==="
python -m research.scripts.build_lora_sft_dataset \
  --experiment lora-no-inject \
  --runs-dir "${PROJECT}/research/runs" \
  --output "${DATA}"

echo "=== Training LoRA-no-inject ==="
python -m research.scripts.train_lora_sft \
  --data "${DATA}" \
  --output-dir "${OUT}" \
  --model Qwen/Qwen3-1.7B \
  --epochs 3 \
  --batch-size 4 \
  --grad-accum 4

echo "=== Done ==="
ls -lh "${OUT}" | head
