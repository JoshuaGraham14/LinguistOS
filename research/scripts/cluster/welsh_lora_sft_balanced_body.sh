#!/bin/bash
# Shared trainer for balanced Welsh LoRA-{no-inject,form} SFT runs.
set -euo pipefail

PROJECT=/vol/bitbucket/jjg25/LinguistOS-welsh
MAIN=/vol/bitbucket/jjg25/LinguistOS
: "${EXPERIMENT:?Set EXPERIMENT to lora-no-inject or lora-form}"

case "${EXPERIMENT}" in
  lora-no-inject)
    DATA="${PROJECT}/research/runs/lora_welsh/sft_lora_no_inject_n150_balanced_2000_each.jsonl"
    OUT="${PROJECT}/research/runs/lora_welsh/adapters/qwen3_1p7b_lora_no_inject_balanced_2k_each"
    ;;
  lora-form)
    DATA="${PROJECT}/research/runs/lora_welsh/sft_lora_form_n150_balanced_2000_each.jsonl"
    OUT="${PROJECT}/research/runs/lora_welsh/adapters/qwen3_1p7b_lora_form_balanced_2k_each"
    ;;
  *)
    echo "ERROR: unsupported EXPERIMENT=${EXPERIMENT}" >&2
    exit 1
    ;;
esac

mkdir -p "${PROJECT}/logs" "${PROJECT}/research/runs/lora_welsh/adapters"

if [[ -f "${MAIN}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${MAIN}/.venv/bin/activate"
elif [[ -f "${PROJECT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${PROJECT}/.venv/bin/activate"
else
  echo "ERROR: no usable venv" >&2
  exit 1
fi

cd "${PROJECT}"
# shellcheck disable=SC1091
source "${PROJECT}/research/scripts/cluster/research_cache_env.sh"
export PYTHONPATH="${PROJECT}:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false

python3 - <<'PY'
import importlib.util
missing = [p for p in ("peft", "trl", "datasets") if importlib.util.find_spec(p) is None]
if missing:
    raise SystemExit(f"Missing training dependencies: {missing}")
print("training dependencies: ok")
PY

if [[ ! -f "${DATA}" ]]; then
  echo "ERROR: missing balanced SFT dataset: ${DATA}" >&2
  exit 1
fi
if [[ -e "${OUT}/adapter_config.json" ]]; then
  echo "ERROR: completed adapter already exists: ${OUT}" >&2
  exit 1
fi

DATA_PATH="${DATA}" python3 - <<'PY'
import json
import os
from collections import Counter

path = os.environ["DATA_PATH"]
counts = Counter()
with open(path, encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        counts[row["constraints"]["construction"]] += 1
print("dataset construction counts:", dict(counts))
if counts != Counter({"synthetic": 2000, "periphrastic": 2000}):
    raise SystemExit(f"Expected exactly 2000 per construction, got {dict(counts)}")
PY

echo "=== Welsh ${EXPERIMENT} balanced LoRA SFT — $(date -Is) ==="
echo "  host=$(hostname) job=${SLURM_JOB_ID:-interactive}"
echo "  data=${DATA}"
echo "  output=${OUT}"
echo "  base=Qwen/Qwen3-1.7B epochs=3 rank=16 alpha=32"
echo "  raw split: train=3800 (1900/1900), val=200 (100/100)"
echo "  oversampling disabled to preserve balance"

python3 -m research.scripts.train_lora_sft \
  --data "${DATA}" \
  --output-dir "${OUT}" \
  --model Qwen/Qwen3-1.7B \
  --epochs 3 \
  --batch-size 4 \
  --grad-accum 4 \
  --oversample-factor 1 \
  --stratify-construction

echo "=== done $(date -Is) ==="
ls -lh "${OUT}"
