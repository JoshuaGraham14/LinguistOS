#!/bin/bash
# Train Qwen3-0.6B LoRA Experiment A (form given). Writes ONLY under
# research/runs/lora_06b/ — does not touch 1.7B adapters or DBs.
#
# Reuses read-only SFT JSONL from research/runs/lora/ when present; otherwise
# builds it without changing 1.7B adapter dirs.
#
# Usage:
#   sbatch research/scripts/cluster/lora_06b_sft_form.sh

#SBATCH --job-name=lora06_form
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --partition=a30
#SBATCH --time=12:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jjg25
#SBATCH --output=/vol/bitbucket/jjg25/LinguistOS/logs/lora_06b_sft_form_%j.out

set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS
VENV="${PROJECT}/.venv"
cd "${PROJECT}"

DATA="${PROJECT}/research/runs/lora/sft_lora_form_n150.jsonl"
LEGACY_DATA="${PROJECT}/research/runs/lora/sft_form_given_n150.jsonl"
OUT="${PROJECT}/research/runs/lora_06b/adapters/lora_form"

mkdir -p "${PROJECT}/logs" "${OUT}"

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

if [[ -f "${DATA}" ]]; then
  echo "=== Reusing existing SFT JSONL (read-only): ${DATA} ==="
elif [[ -f "${LEGACY_DATA}" ]]; then
  DATA="${LEGACY_DATA}"
  echo "=== Reusing legacy SFT JSONL (read-only): ${DATA} ==="
else
  echo "=== Building SFT dataset (LoRA-form) — missing ${DATA} ==="
  python -m research.scripts.build_lora_sft_dataset \
    --experiment lora-form \
    --runs-dir "${PROJECT}/research/runs" \
    --output "${DATA}"
fi

echo "=== Training LoRA-form on Qwen3-0.6B ==="
echo "  data=${DATA}"
echo "  output=${OUT}"
python -m research.scripts.train_lora_sft \
  --data "${DATA}" \
  --output-dir "${OUT}" \
  --model Qwen/Qwen3-0.6B \
  --epochs 3 \
  --batch-size 4 \
  --grad-accum 4

echo "=== Done ==="
ls -lh "${OUT}" | head
